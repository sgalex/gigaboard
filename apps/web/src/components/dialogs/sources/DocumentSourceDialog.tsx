/**
 * Document Source Dialog — fullscreen диалог для загрузки документов (PDF, DOCX, TXT)
 * с итеративным AI-чатом для извлечения данных.
 * 
 * Layout (fullscreen):
 * - Левая панель (40%): загрузка файла + анализ + чат с мультиагентом
 * - Правая панель (60%): результат — текст / таблицы (обновляются по мере AI-чата)
 * 
 * Паттерн чата аналогичен TransformDialog / WidgetDialog.
 * 
 * См. docs/SOURCE_NODE_CONCEPT.md — раздел "📄 4. Document Dialog"
 */
import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import {
    FileText, Upload, Check, Loader2, X, FileType, Table2,
    AlignLeft, AlertTriangle, Send, MessageSquare, Trash2, Lightbulb, RefreshCw,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { SourceNode, SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { filesAPI } from '@/services/api'
import { cn } from '@/lib/utils'
import { MultiAgentProgressBlock } from '@/components/shared/MultiAgentProgressBlock'
import {
    type ProgressStep as SharedProgressStep,
    type ProgressMeta as SharedProgressMeta,
    mergePlanSteps,
    applyProgressToSteps,
    metaFromSteps,
    markRunningAsCompleted,
    markLastRunningAsFailed,
} from '@/lib/multiAgentProgress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'
import { DocumentSuggestionsPanel } from './DocumentSuggestionsPanel'
import { logDocumentExtractionMultiAgentTrace } from '@/lib/documentExtractionTrace'
import { rowToCellStrings } from '@/lib/tablePreview'
import { getErrorMessage } from '@/lib/errors'

// ─── Types ──────────────────────────────────────────────────────────────────

interface DocumentAnalysisResult {
    document_type: string
    filename: string
    text: string
    text_length: number
    page_count: number | null
    tables: Array<{
        name: string
        columns: Array<{ name: string; type: string }>
        rows: Array<Record<string, any>>
        row_count: number
    }>
    table_count: number
    total_rows: number
    is_scanned: boolean
    file_id: string
}

interface ChatMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    contentType?: 'text' | 'markdown'
    timestamp: Date
}

// ─── Constants ──────────────────────────────────────────────────────────────

const DOC_TYPE_LABELS: Record<string, string> = {
    pdf: 'PDF',
    docx: 'Word (DOCX)',
    txt: 'Текстовый файл',
}

const DOC_TYPE_COLORS: Record<string, string> = {
    pdf: 'text-red-500',
    docx: 'text-blue-500',
    txt: 'text-gray-500',
}

/** Лимит длины цепочки для API (TransformDialog не режет на клиенте — здесь ограничиваем размер тела запроса). */
const AGENT_CHAT_HISTORY_LIMIT = 20

/**
 * Нормализация ролей и обрезка хвоста — после сборки fullChatHistory как в TransformDialog.
 * См. `TransformDialog` → handleSendMessage: `fullChatHistory = [...chatMessages, currentUser]`.
 */
function buildAgentChatHistory(
    messages: { role: string; content: string }[]
): { role: string; content: string }[] {
    return messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content }))
        .slice(-AGENT_CHAT_HISTORY_LIMIT)
}

function buildAnalysisFromDocumentSource(existing: SourceNode): DocumentAnalysisResult | null {
    const cfg = existing.config || {}
    const content = existing.content || {}
    const text = typeof content.text === 'string' ? content.text : ''
    const fid = cfg.file_id
    if (!fid) return null

    const rawTables = Array.isArray(content.tables) ? content.tables : []
    const tables: DocumentAnalysisResult['tables'] = rawTables.map((t, idx) => {
        const columns = (t.columns || []).map((c: { name?: string; type?: string }) => ({
            name: typeof c === 'object' && c ? String(c.name || '') : String(c),
            type: typeof c === 'object' && c ? String(c.type || 'string') : 'string',
        }))
        const rows = Array.isArray(t.rows) ? t.rows : []
        const row_count = typeof t.row_count === 'number' ? t.row_count : rows.length
        return {
            name: t.name || `table_${idx + 1}`,
            columns,
            rows,
            row_count,
        }
    })
    const total_rows = tables.reduce(
        (acc, t) => acc + (t.row_count || t.rows?.length || 0),
        0
    )

    return {
        document_type: String(cfg.document_type || 'pdf'),
        filename: String(cfg.filename || existing.metadata?.name || 'document'),
        text,
        text_length: text.length,
        page_count: cfg.page_count ?? null,
        tables,
        table_count: tables.length,
        total_rows,
        is_scanned: !!cfg.is_scanned,
        file_id: String(fid),
    }
}

function buildHydratedChatMessages(
    cfg: Record<string, unknown>,
    analysis: DocumentAnalysisResult
): ChatMessage[] {
    const summaryMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: analysis.is_scanned
            ? `📄 **${analysis.filename}** — скан-документ, текстовый слой не найден.\n\nOCR через GigaChat будет доступен в следующих версиях.`
            : `📄 Документ **${analysis.filename}** загружен из источника:\n\n` +
              `- Тип: ${DOC_TYPE_LABELS[analysis.document_type] || analysis.document_type}\n` +
              (analysis.page_count ? `- Страниц: ${analysis.page_count}\n` : '') +
              `- Текст: ${analysis.text_length.toLocaleString()} символов\n` +
              `- Таблиц: ${analysis.table_count}` +
              (analysis.total_rows > 0 ? ` (${analysis.total_rows} строк)` : '') +
              `\n\nОпишите, какие данные извлечь из документа.`,
        contentType: 'markdown',
        timestamp: new Date(),
    }
    const out: ChatMessage[] = [summaryMsg]
    const ep = cfg.extraction_prompt
    if (typeof ep === 'string' && ep.trim()) {
        out.push({
            id: crypto.randomUUID(),
            role: 'user',
            content: ep.trim(),
            timestamp: new Date(),
        })
    }
    return out
}

// ─── Component ──────────────────────────────────────────────────────────────

export function DocumentSourceDialog({ open, onOpenChange, initialPosition, existingSource, mode = 'create' }: SourceDialogProps) {
    // ── File & Analysis state ─────────────────────────────────────
    const [file, setFile] = useState<File | null>(null)
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [analysis, setAnalysis] = useState<DocumentAnalysisResult | null>(null)

    // ── Chat state ────────────────────────────────────────────────
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
    const [inputValue, setInputValue] = useState('')
    const [isGenerating, setIsGenerating] = useState(false)
    const [progressSteps, setProgressSteps] = useState<SharedProgressStep[]>([])
    const [progressMeta, setProgressMeta] = useState<SharedProgressMeta>({ current: 0, total: null })

    // ── Results state (right panel, updated by AI chat) ───────────
    const [extractedTables, setExtractedTables] = useState<DocumentAnalysisResult['tables']>([])
    const [activeTab, setActiveTab] = useState<'text' | 'tables'>('text')
    const [activeTableIdx, setActiveTableIdx] = useState(0)
    const [showFullText, setShowFullText] = useState(false)

    const [composerTab, setComposerTab] = useState<'message' | 'suggestions'>('message')
    const [composerSuggestionsRefreshKey, setComposerSuggestionsRefreshKey] = useState(0)
    const [composerSuggestionsLoading, setComposerSuggestionsLoading] = useState(false)

    // ── Refs ──────────────────────────────────────────────────────
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    // ── Source dialog hook ────────────────────────────────────────
    const resetForm = useCallback(() => {
        setFile(null)
        setAnalysis(null)
        setChatMessages([])
        setInputValue('')
        setExtractedTables([])
        setProgressSteps([])
        setProgressMeta({ current: 0, total: null })
        setActiveTab('text')
        setActiveTableIdx(0)
        setShowFullText(false)
        setComposerTab('message')
        setComposerSuggestionsRefreshKey(0)
        setComposerSuggestionsLoading(false)
    }, [])

    const { isLoading, create, update } = useSourceDialog({
        sourceType: SourceType.DOCUMENT,
        onClose: () => {
            resetForm()
            onOpenChange(false)
        },
        position: initialPosition,
    })

    const isEditMode = mode === 'edit' && !!existingSource
    const existingSourceRef = useRef<SourceNode | undefined>(undefined)
    useEffect(() => {
        existingSourceRef.current = existingSource
    }, [existingSource])

    useEffect(() => {
        if (!open) {
            resetForm()
            return
        }
        if (!isEditMode) return
        const src = existingSourceRef.current
        if (!src) return
        const built = buildAnalysisFromDocumentSource(src)
        if (!built) {
            notify.info('Не удалось восстановить документ: нет file_id в конфигурации источника.')
            return
        }
        setAnalysis(built)
        setExtractedTables(built.tables)
        setChatMessages(
            buildHydratedChatMessages(
                (src.config || {}) as Record<string, unknown>,
                built
            )
        )
        setInputValue('')
        setProgressSteps([])
        setProgressMeta({ current: 0, total: null })
        setActiveTab(built.table_count > 0 ? 'tables' : 'text')
        setActiveTableIdx(0)
        setShowFullText(false)
        setComposerTab('message')
        setComposerSuggestionsRefreshKey(0)
        setComposerSuggestionsLoading(false)
    }, [open, isEditMode, existingSource?.id, resetForm])

    const chatHistoryForSuggestions = useMemo(
        () => chatMessages.map((msg) => ({ role: msg.role, content: msg.content })),
        [chatMessages]
    )

    const documentSuggestionsFingerprint = useMemo(() => {
        if (!analysis?.file_id) return ''
        const sig = extractedTables.map((t) => `${t.name}:${t.row_count ?? 0}`).join('|')
        return `${analysis.file_id}|${analysis.text_length}|${sig}`
    }, [analysis?.file_id, analysis?.text_length, extractedTables])

    const documentSuggestionsPayload = useMemo(() => {
        if (!analysis) return null
        return {
            document_text: analysis.text,
            document_type: analysis.document_type,
            filename: analysis.filename,
            page_count: analysis.page_count,
            existing_tables: extractedTables as unknown as Array<Record<string, unknown>>,
        }
    }, [analysis, extractedTables])

    // ── Auto-scroll chat ─────────────────────────────────────────
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [chatMessages, isGenerating, progressSteps.length, progressMeta.current])

    // ═══════════════════════════════════════════════════════════════
    //  File Upload & Analysis
    // ═══════════════════════════════════════════════════════════════

    const handleFileDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        const droppedFile = e.dataTransfer.files[0]
        if (droppedFile) {
            const ext = droppedFile.name.split('.').pop()?.toLowerCase()
            if (ext && ['pdf', 'docx', 'txt', 'md'].includes(ext)) {
                setFile(droppedFile)
                analyzeFile(droppedFile)
            } else {
                notify.error('Поддерживаются только PDF, DOCX и TXT')
            }
        }
    }, [])

    const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0]
        if (!selectedFile) return
        const ext = selectedFile.name.split('.').pop()?.toLowerCase()
        if (ext && ['pdf', 'docx', 'txt', 'md'].includes(ext)) {
            setFile(selectedFile)
            analyzeFile(selectedFile)
        } else {
            notify.error('Поддерживаются только PDF, DOCX и TXT')
            e.target.value = ''
        }
    }, [])

    const analyzeFile = async (file: File) => {
        setIsAnalyzing(true)
        setAnalysis(null)
        setChatMessages([])
        setExtractedTables([])
        try {
            // 1. Upload file
            notify.info('Загрузка документа...')
            const uploadResponse = await filesAPI.upload(file)
            const uploadedFile = uploadResponse.data

            // 2. Analyze document
            notify.info('Извлечение текста и таблиц...')
            const analysisResponse = await filesAPI.analyzeDocument(uploadedFile.file_id)
            const result = analysisResponse.data

            const analysisResult: DocumentAnalysisResult = {
                ...result,
                file_id: uploadedFile.file_id,
            }

            setAnalysis(analysisResult)
            setExtractedTables(result.tables || [])

            // Auto-switch to tables tab if tables found
            if (result.table_count > 0) {
                setActiveTab('tables')
            }

            // Add system message about analysis
            const summaryMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: result.is_scanned
                    ? `📄 **${file.name}** — скан-документ, текстовый слой не найден.\n\nOCR через GigaChat будет доступен в следующих версиях.`
                    : `📄 Документ **${file.name}** проанализирован:\n\n` +
                    `- Тип: ${DOC_TYPE_LABELS[result.document_type] || result.document_type}\n` +
                    (result.page_count ? `- Страниц: ${result.page_count}\n` : '') +
                    `- Текст: ${result.text_length.toLocaleString()} символов\n` +
                    `- Таблиц: ${result.table_count}` +
                    (result.total_rows > 0 ? ` (${result.total_rows} строк)` : '') +
                    `\n\nОпишите, какие данные извлечь из документа.`,
                contentType: 'markdown',
                timestamp: new Date(),
            }
            setChatMessages([summaryMsg])

            const msg = result.is_scanned
                ? 'Документ — скан, текстовый слой не найден'
                : `Извлечено: ${result.text_length.toLocaleString()} символов, ${result.table_count} таблиц`
            notify.success(msg)
        } catch (error) {
            notify.error(getErrorMessage(error, 'Ошибка анализа документа'))
            console.error('Document analysis error:', error)
        } finally {
            setIsAnalyzing(false)
        }
    }

    // ═══════════════════════════════════════════════════════════════
    //  Chat — Multi-Agent extraction
    // ═══════════════════════════════════════════════════════════════

    const handleSendMessage = async (messageText?: string) => {
        const textToSend = (messageText ?? inputValue).trim()
        if (!textToSend || isGenerating || !analysis) return

        // 1. Add user message
        const userMessage: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'user',
            content: textToSend,
            timestamp: new Date(),
        }
        setChatMessages(prev => [...prev, userMessage])
        setInputValue('')
        setIsGenerating(true)
        setProgressSteps([])
        setProgressMeta({ current: 0, total: null })

        try {
            // Как в TransformDialog: полная цепочка включая текущее user-сообщение, затем нормализация/лимит.
            const fullChatHistory = [
                ...chatMessages.map((msg) => ({
                    role: msg.role,
                    content: msg.content,
                })),
                { role: userMessage.role, content: userMessage.content },
            ]
            const chatHistoryForAgent = buildAgentChatHistory(fullChatHistory)

            let data: {
                narrative?: string
                tables?: DocumentAnalysisResult['tables']
                session_id?: string
                trace_file_path?: string
                execution_time_ms?: number
            } | null = null
            let streamError: string | null = null

            await filesAPI.extractDocumentChatStream(
                analysis.file_id,
                {
                    user_prompt: userMessage.content,
                    document_text: analysis.text,
                    document_type: analysis.document_type,
                    filename: analysis.filename,
                    page_count: analysis.page_count,
                    existing_tables: extractedTables,
                    chat_history: chatHistoryForAgent,
                },
                {
                    onPlanUpdate: (steps, meta) => {
                        setProgressSteps((prev) => {
                            const next = mergePlanSteps(prev, steps, meta?.completedCount, 'document')
                            setProgressMeta(metaFromSteps(next))
                            return next
                        })
                    },
                    onProgress: (_agentLabel, task, meta) => {
                        setProgressSteps((prev) => {
                            const next = applyProgressToSteps(
                                prev,
                                task,
                                meta?.stepIndex,
                                'document'
                            )
                            let metaNext = metaFromSteps(next)
                            if (
                                typeof meta?.totalSteps === 'number' &&
                                meta.totalSteps > 0 &&
                                metaNext.total != null
                            ) {
                                metaNext = {
                                    ...metaNext,
                                    total: Math.max(metaNext.total, meta.totalSteps),
                                }
                            }
                            setProgressMeta(metaNext)
                            return next
                        })
                    },
                    onResult: (result) => {
                        data = result as typeof data
                        const r = result as Record<string, unknown>
                        logDocumentExtractionMultiAgentTrace({
                            fileId: analysis.file_id,
                            sessionId: typeof r.session_id === 'string' ? r.session_id : null,
                            traceFilePath:
                                typeof r.trace_file_path === 'string' ? r.trace_file_path : null,
                            executionTimeMs:
                                typeof r.execution_time_ms === 'number'
                                    ? r.execution_time_ms
                                    : null,
                            tableCount: Array.isArray(r.tables) ? r.tables.length : 0,
                            narrativePreview:
                                typeof r.narrative === 'string'
                                    ? r.narrative.slice(0, 280)
                                    : undefined,
                        })
                    },
                    onError: (errorText) => {
                        streamError = errorText
                    },
                }
            )

            if (streamError) {
                throw new Error(streamError)
            }
            if (!data) {
                throw new Error('Пустой ответ извлечения')
            }

            // 4. Add AI response
            setProgressSteps((prev) => {
                const next = markRunningAsCompleted(prev)
                setProgressMeta(metaFromSteps(next))
                return next
            })

            const aiMessage: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: data.narrative || 'Анализ выполнен.',
                contentType: 'markdown',
                timestamp: new Date(),
            }
            setChatMessages(prev => [...prev, aiMessage])

            // 5. Update extracted tables if AI returned new ones
            if (data.tables && data.tables.length > 0) {
                setExtractedTables(prev => {
                    const merged = [...prev]
                    for (const newTable of data.tables) {
                        const existingIdx = merged.findIndex(t => t.name === newTable.name)
                        if (existingIdx >= 0) {
                            merged[existingIdx] = newTable as DocumentAnalysisResult['tables'][number]
                        } else {
                            merged.push(newTable as DocumentAnalysisResult['tables'][number])
                        }
                    }
                    const firstNewName = data.tables[0]?.name
                    const idx = firstNewName
                        ? merged.findIndex(t => t.name === firstNewName)
                        : -1
                    if (idx >= 0) {
                        queueMicrotask(() => setActiveTableIdx(idx))
                    }
                    return merged
                })
                setActiveTab('tables')
            }
        } catch (error: any) {
            setProgressSteps((prev) => markLastRunningAsFailed(prev))
            const errorText = error?.response?.data?.detail || error?.message || 'Неизвестная ошибка'
            const errorMessage: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: `❌ Ошибка: ${errorText}`,
                timestamp: new Date(),
            }
            setChatMessages(prev => [...prev, errorMessage])
        } finally {
            setIsGenerating(false)
        }
    }

    const handleClearChatHistory = () => {
        if (isGenerating || isAnalyzing) return
        // Оставляем первое сообщение ассистента (итог анализа файла), сбрасываем диалог.
        setChatMessages((prev) => (prev.length > 0 ? [prev[0]] : []))
    }

    const canClearChatHistory =
        !!analysis &&
        !isGenerating &&
        !isAnalyzing &&
        chatMessages.some((m) => m.role === 'user')

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSendMessage()
        }
    }

    // ═══════════════════════════════════════════════════════════════
    //  Submit — Create Source Node
    // ═══════════════════════════════════════════════════════════════

    const handleSubmit = async () => {
        if (!analysis) {
            notify.error('Загрузите и проанализируйте документ')
            return
        }

        try {
            const config = {
                file_id: analysis.file_id,
                filename: analysis.filename,
                document_type: analysis.document_type,
                mime_type: file?.type || undefined,
                size_bytes: file?.size || undefined,
                is_scanned: analysis.is_scanned,
                extraction_prompt: chatMessages
                    .filter(m => m.role === 'user')
                    .map(m => m.content)
                    .join('\n') || undefined,
            }

            const metadata = {
                name:
                    (isEditMode && existingSource?.metadata?.name) ||
                    file?.name?.replace(/\.(pdf|docx|txt|md)$/i, '') ||
                    analysis.filename.replace(/\.(pdf|docx|txt|md)$/i, '') ||
                    analysis.filename,
            }

            const normalizedTables = extractedTables.map((table, idx) => ({
                name: table.name || `table_${idx + 1}`,
                columns: table.columns || [],
                rows: table.rows || [],
                row_count: table.row_count ?? (table.rows?.length || 0),
                column_count: table.columns?.length || 0,
            }))
            const sourceData = {
                text: analysis.text || '',
                tables: normalizedTables,
            }

            if (mode === 'edit' && existingSource) {
                await update(existingSource.id, config, metadata, sourceData)
            } else {
                await create(config, metadata, sourceData)
                notify.success(`Источник «${file?.name}» создан`)
            }
        } catch (error) {
            notify.error('Не удалось создать источник')
            console.error('Document source error:', error)
        }
    }

    // ═══════════════════════════════════════════════════════════════
    //  Helpers — Render
    // ═══════════════════════════════════════════════════════════════

    const renderMessageContent = (msg: ChatMessage) => {
        const { content, contentType = 'text' } = msg
        if (contentType === 'markdown') {
            return (
                <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {content}
                    </ReactMarkdown>
                </div>
            )
        }
        return <span className="whitespace-pre-wrap break-words">{content}</span>
    }

    const isValid = !!analysis
    const displayFileName = file?.name || analysis?.filename || 'загрузите файл'
    const dialogTitle =
        isEditMode && existingSource?.metadata?.name
            ? `Документ — ${existingSource.metadata.name}`
            : `Документ — ${displayFileName}`
    const hasDocumentLoaded = !!(file || analysis)
    /** Пустой чат без активных процессов — без overflow-y, иначе h-full + якорь дают лишний скролл */
    const chatNeedsMessageScroll =
        chatMessages.length > 0 || isAnalyzing || isGenerating

    // ═══════════════════════════════════════════════════════════════
    //  Render
    // ═══════════════════════════════════════════════════════════════

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title={dialogTitle}
            description="Загрузите документ → AI извлечёт текст и таблицы через итеративный чат"
            icon={<FileText className="h-5 w-5 text-blue-500" />}
            isLoading={isLoading}
            isValid={isValid}
            onSubmit={handleSubmit}
            submitLabel={mode === 'edit' ? 'Сохранить' : '📄 Создать источник'}
            className="w-[calc(100vw-2rem)] max-w-[calc(100vw-2rem)] h-[calc(100vh-2rem)]"
            contentClassName="overflow-hidden !py-0 min-h-0"
        >
            <div className="flex flex-1 min-h-0">
                {/* ═══ LEFT PANEL (40%) — Upload + Chat ═══ */}
                <div className="w-[40%] border-r flex flex-col min-h-0">
                    {/* ── File Upload / File Info ── */}
                    <div className="p-3 border-b shrink-0">
                        {mode === 'create' && !hasDocumentLoaded ? (
                            <div
                                onDragOver={(e) => e.preventDefault()}
                                onDrop={handleFileDrop}
                                className="border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-primary/50 transition-colors cursor-pointer"
                                onClick={() => document.getElementById('doc-file-input')?.click()}
                            >
                                <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                                <p className="text-sm font-medium mb-1">Перетащите документ сюда</p>
                                <p className="text-xs text-muted-foreground">PDF, DOCX или TXT</p>
                                <Input
                                    id="doc-file-input"
                                    type="file"
                                    accept=".pdf,.docx,.txt,.md"
                                    onChange={handleFileSelect}
                                    className="hidden"
                                />
                            </div>
                        ) : hasDocumentLoaded ? (
                            <div className="flex items-center gap-2">
                                <FileText className={cn('h-4 w-4', analysis ? DOC_TYPE_COLORS[analysis.document_type] || 'text-blue-500' : 'text-blue-500')} />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium truncate">{file?.name || analysis?.filename}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {file ? `${(file.size / 1024).toFixed(1)} KB` : 'Файл из источника'}
                                        {analysis && ` · ${DOC_TYPE_LABELS[analysis.document_type] || analysis.document_type}`}
                                        {analysis?.page_count != null && ` · ${analysis.page_count} стр.`}
                                        {analysis && ` · ${analysis.text_length.toLocaleString()} символов`}
                                    </p>
                                </div>
                                {isAnalyzing && <Loader2 className="h-4 w-4 animate-spin text-blue-500 shrink-0" />}
                                {analysis && <Check className="h-4 w-4 text-green-500 shrink-0" />}
                                {!isAnalyzing && (
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-7 w-7 p-0 shrink-0"
                                        onClick={() => {
                                            resetForm()
                                        }}
                                    >
                                        <X className="h-3.5 w-3.5" />
                                    </Button>
                                )}
                            </div>
                        ) : null}

                        {analysis?.is_scanned && (
                            <div className="mt-2 p-2 bg-yellow-500/10 border border-yellow-500/20 rounded text-xs text-yellow-600 flex items-start gap-2">
                                <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                                Документ — скан. Текстовый слой не найден.
                            </div>
                        )}
                    </div>

                    <div className="px-3 py-1.5 bg-muted/40 text-xs text-muted-foreground border-b shrink-0 flex items-center justify-between gap-2">
                        <span>Опишите, какие данные нужно извлечь из документа</span>
                        {canClearChatHistory && (
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive shrink-0"
                                onClick={handleClearChatHistory}
                                title="Очистить историю диалога"
                            >
                                <Trash2 className="w-3 h-3 mr-1" />
                                Очистить
                            </Button>
                        )}
                    </div>

                    {/* ── Chat Messages ── */}
                    <div
                        className={cn(
                            'flex-1 min-h-0 px-3 pb-3 flex flex-col',
                            chatNeedsMessageScroll
                                ? 'overflow-y-auto space-y-2'
                                : 'overflow-hidden justify-center py-4'
                        )}
                    >
                        {!chatNeedsMessageScroll ? (
                            <div className="flex flex-col items-center justify-center text-center text-muted-foreground shrink-0">
                                <MessageSquare className="w-10 h-10 mb-3 text-blue-500/30" />
                                <p className="text-sm">Загрузите документ, чтобы начать</p>
                                <p className="text-xs mt-1 text-muted-foreground/70">
                                    AI проанализирует текст и поможет извлечь таблицы
                                </p>
                            </div>
                        ) : (
                            <>
                                <div className="space-y-2 pt-2">
                                    {chatMessages.map((msg) => (
                                        <div
                                            key={msg.id}
                                            className={cn(
                                                'flex',
                                                msg.role === 'user' ? 'justify-end' : 'justify-start'
                                            )}
                                        >
                                            <div
                                                className={cn(
                                                    'max-w-[90%] rounded-lg px-3 py-2 text-sm',
                                                    msg.role === 'user'
                                                        ? 'bg-primary/15'
                                                        : 'bg-muted'
                                                )}
                                            >
                                                {renderMessageContent(msg)}
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {isAnalyzing && (
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Извлечение текста и таблиц из документа...
                                    </div>
                                )}

                                {isGenerating && (
                                    <MultiAgentProgressBlock
                                        runningText="AI извлекает данные из документа..."
                                        progressMeta={progressMeta}
                                        progressSteps={progressSteps}
                                        variant="blue"
                                    />
                                )}

                                <div ref={messagesEndRef} />
                            </>
                        )}
                    </div>

                    {/* ── Сообщение / рекомендации (как TransformDialog) ── */}
                    <div className="border-t flex flex-col shrink-0 min-h-0">
                        <Tabs
                            value={composerTab}
                            onValueChange={(v) => setComposerTab(v as 'message' | 'suggestions')}
                            className="flex flex-col gap-0 outline-none focus-visible:outline-none"
                        >
                            <TabsList className="mx-2 mt-2 h-8 w-[calc(100%-1rem)] grid grid-cols-2 shrink-0 gap-1 p-1 items-stretch">
                                <TabsTrigger value="message" className="text-xs gap-1 px-2 h-full min-h-0">
                                    <MessageSquare className="h-3 w-3 shrink-0" />
                                    Сообщение
                                </TabsTrigger>
                                <div
                                    className={cn(
                                        'flex min-h-0 min-w-0 h-full rounded-sm overflow-hidden',
                                        composerTab === 'suggestions' &&
                                            'bg-background text-foreground shadow-sm'
                                    )}
                                >
                                    <TabsTrigger
                                        value="suggestions"
                                        className="text-xs gap-1 px-2 h-full min-w-0 flex-1 rounded-none shadow-none data-[state=active]:bg-transparent data-[state=active]:shadow-none"
                                        disabled={!analysis}
                                    >
                                        <Lightbulb className="h-3 w-3 shrink-0" />
                                        <span className="truncate">Рекомендации</span>
                                    </TabsTrigger>
                                    <button
                                        type="button"
                                        className={cn(
                                            'inline-flex items-center justify-center w-7 shrink-0 rounded-none border-l border-border/60',
                                            'text-muted-foreground hover:text-foreground hover:bg-muted/50',
                                            'disabled:pointer-events-none disabled:opacity-40',
                                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1'
                                        )}
                                        disabled={
                                            composerTab !== 'suggestions' ||
                                            !analysis ||
                                            isGenerating ||
                                            isAnalyzing ||
                                            composerSuggestionsLoading
                                        }
                                        onClick={() => setComposerSuggestionsRefreshKey((k) => k + 1)}
                                        title="Обновить рекомендации"
                                        aria-label="Обновить рекомендации"
                                    >
                                        <RefreshCw className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            </TabsList>
                            <TabsContent
                                value="message"
                                className="mt-0 p-2 pt-1 m-0 border-0 outline-none focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 data-[state=inactive]:hidden"
                            >
                                <div className="flex gap-2 items-end">
                                    <Textarea
                                        ref={textareaRef}
                                        value={inputValue}
                                        onChange={(e) => setInputValue(e.target.value)}
                                        onKeyDown={handleKeyDown}
                                        placeholder={
                                            !analysis
                                                ? 'Сначала загрузите документ...'
                                                : 'Опишите, какие данные извлечь...'
                                        }
                                        className="min-h-[44px] max-h-[100px] resize-none"
                                        disabled={!analysis || isGenerating || isAnalyzing}
                                        rows={1}
                                    />
                                    <Button
                                        onClick={() => handleSendMessage()}
                                        disabled={!inputValue.trim() || isGenerating || !analysis}
                                        size="icon"
                                        className="h-[44px] w-[44px] shrink-0"
                                    >
                                        {isGenerating ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <Send className="w-4 h-4" />
                                        )}
                                    </Button>
                                </div>
                            </TabsContent>
                            <TabsContent
                                value="suggestions"
                                forceMount
                                className="mt-0 m-0 p-2 pt-1 flex-none h-fit min-h-0 max-h-[min(36vh,260px)] overflow-y-auto border-0 outline-none focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 data-[state=inactive]:hidden"
                            >
                                {analysis && documentSuggestionsPayload && (
                                    <DocumentSuggestionsPanel
                                        fileId={analysis.file_id}
                                        documentPayload={documentSuggestionsPayload}
                                        chatHistory={chatHistoryForSuggestions}
                                        contextFingerprint={documentSuggestionsFingerprint}
                                        suggestionsTabActive={composerTab === 'suggestions'}
                                        isGenerating={isGenerating || isAnalyzing}
                                        suggestionsRefreshKey={composerSuggestionsRefreshKey}
                                        onSuggestionsLoadingChange={setComposerSuggestionsLoading}
                                        onSuggestionClick={(prompt) => {
                                            handleSendMessage(prompt)
                                            setComposerTab('message')
                                        }}
                                    />
                                )}
                            </TabsContent>
                        </Tabs>
                    </div>
                </div>

                {/* ═══ RIGHT PANEL (60%) — Extracted Content ═══ */}
                <div className="w-[60%] flex flex-col min-h-0">
                    {analysis ? (
                        <>
                            {/* ── Tabs: Text / Tables ── */}
                            <div className="flex gap-1 px-3 border-b shrink-0">
                                <button
                                    className={cn(
                                        'flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 transition-colors',
                                        activeTab === 'text'
                                            ? 'border-primary text-primary'
                                            : 'border-transparent text-muted-foreground hover:text-foreground'
                                    )}
                                    onClick={() => setActiveTab('text')}
                                >
                                    <AlignLeft className="h-3.5 w-3.5" />
                                    Текст
                                </button>
                                <button
                                    className={cn(
                                        'flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 transition-colors',
                                        activeTab === 'tables'
                                            ? 'border-primary text-primary'
                                            : 'border-transparent text-muted-foreground hover:text-foreground'
                                    )}
                                    onClick={() => setActiveTab('tables')}
                                >
                                    <Table2 className="h-3.5 w-3.5" />
                                    Таблицы
                                    {extractedTables.length > 0 && (
                                        <Badge variant="secondary" className="ml-1 text-xs px-1.5 py-0">
                                            {extractedTables.length}
                                        </Badge>
                                    )}
                                </button>
                            </div>

                            {/* ── Tab Content ── */}
                            <div className="flex-1 overflow-hidden min-h-0">
                                {/* Text Tab */}
                                {activeTab === 'text' && (
                                    <div className="h-full flex flex-col">
                                        <div className="p-3 border-b bg-muted/50 flex items-center justify-between shrink-0">
                                            <div>
                                                <h4 className="text-sm font-medium">Извлечённый текст</h4>
                                                <p className="text-xs text-muted-foreground">
                                                    {analysis.text_length.toLocaleString()} символов
                                                    {analysis.page_count != null && ` · ${analysis.page_count} страниц`}
                                                </p>
                                            </div>
                                            <FileType className={cn('h-4 w-4', DOC_TYPE_COLORS[analysis.document_type] || 'text-muted-foreground')} />
                                        </div>
                                        <div className="flex-1 overflow-y-auto p-3">
                                            <pre className="text-xs whitespace-pre-wrap font-sans leading-relaxed text-foreground/90">
                                                {showFullText ? analysis.text : analysis.text.slice(0, 5000)}
                                            </pre>
                                            {analysis.text.length > 5000 && !showFullText && (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="mt-2 text-xs"
                                                    onClick={() => setShowFullText(true)}
                                                >
                                                    Показать полный текст ({analysis.text_length.toLocaleString()} символов)
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* Tables Tab */}
                                {activeTab === 'tables' && (
                                    <div className="h-full flex flex-col">
                                        {extractedTables.length === 0 ? (
                                            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                                                <Table2 className="h-10 w-10 mb-3 opacity-30" />
                                                <p className="text-sm font-medium">Таблицы не найдены</p>
                                                <p className="text-xs mt-1 max-w-xs text-center">
                                                    Попросите AI извлечь таблицы из документа через чат слева
                                                </p>
                                            </div>
                                        ) : (
                                            <>
                                                {/* Table selector */}
                                                {extractedTables.length > 1 && (
                                                    <div className="flex gap-1 flex-wrap p-3 border-b shrink-0">
                                                        {extractedTables.map((table, idx) => (
                                                            <button
                                                                key={idx}
                                                                className={cn(
                                                                    'px-2.5 py-1 text-xs font-medium rounded transition-colors',
                                                                    activeTableIdx === idx
                                                                        ? 'bg-primary text-primary-foreground'
                                                                        : 'bg-muted text-muted-foreground hover:bg-muted/80'
                                                                )}
                                                                onClick={() => setActiveTableIdx(idx)}
                                                            >
                                                                {table.name}
                                                                <span className="ml-1 opacity-70">
                                                                    ({table.row_count || table.rows?.length || 0})
                                                                </span>
                                                            </button>
                                                        ))}
                                                    </div>
                                                )}

                                                {/* Active table preview */}
                                                {extractedTables[activeTableIdx] && (() => {
                                                    const activeTable = extractedTables[activeTableIdx]
                                                    const colNames = activeTable.columns.map((c) => c.name)
                                                    return (
                                                    <div className="flex-1 flex flex-col min-h-0">
                                                        <div className="p-3 border-b bg-muted/50 shrink-0">
                                                            <h4 className="text-sm font-medium">
                                                                {activeTable.name}
                                                            </h4>
                                                            <p className="text-xs text-muted-foreground">
                                                                {activeTable.columns.length} столбцов
                                                                {' · '}
                                                                {activeTable.row_count || activeTable.rows?.length || 0} строк
                                                                {activeTable.rows?.length < (activeTable.row_count || 0) && (
                                                                    <> (показано {activeTable.rows.length})</>
                                                                )}
                                                            </p>
                                                        </div>
                                                        <div className="flex-1 overflow-auto">
                                                            <table className="w-full text-xs">
                                                                <thead className="bg-muted/50 sticky top-0">
                                                                    <tr>
                                                                        {activeTable.columns.map((col, i) => (
                                                                            <th key={i} className="p-2 text-left font-medium border-b whitespace-nowrap">
                                                                                {col.name}
                                                                                <span className="ml-1 text-muted-foreground font-normal">
                                                                                    ({col.type})
                                                                                </span>
                                                                            </th>
                                                                        ))}
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    {activeTable.rows.map((row, rowIdx) => {
                                                                        const cells = rowToCellStrings(row, colNames)
                                                                        return (
                                                                            <tr key={rowIdx} className="border-b hover:bg-muted/30">
                                                                                {cells.map((cell, colIdx) => (
                                                                                    <td key={colIdx} className="p-2 truncate max-w-[200px]">
                                                                                        {cell}
                                                                                    </td>
                                                                                ))}
                                                                            </tr>
                                                                        )
                                                                    })}
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                    )
                                                })()}
                                            </>
                                        )}
                                    </div>
                                )}
                            </div>
                        </>
                    ) : (
                        /* Empty state — no document loaded */
                        <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                            <FileText className="h-12 w-12 mb-3 opacity-20" />
                            <p className="text-sm font-medium">Загрузите документ для анализа</p>
                            <p className="text-xs mt-1">PDF, DOCX или TXT — AI извлечёт текст и таблицы</p>
                        </div>
                    )}
                </div>
            </div>
        </BaseSourceDialog>
    )
}
