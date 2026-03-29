import { useState, useRef, useEffect, useMemo } from 'react'
import Editor from '@monaco-editor/react'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Code, Loader2, Send, Eye, Save, Trash2, Sparkles, MessageSquare, Lightbulb, RefreshCw } from 'lucide-react'
import { ContentNode } from '@/types'
import { cn } from '@/lib/utils'
import { TransformSuggestionsPanel } from './TransformSuggestionsPanel'
import { contentNodesAPI } from '@/services/api'
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

interface TransformDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    sourceNode?: ContentNode
    sourceNodes?: ContentNode[]
    onTransform: (
        code: string,
        transformationId: string,
        description?: string,
        chatHistory?: Array<{ role: 'user' | 'assistant'; content: string }>
    ) => Promise<void>
    // Edit mode
    initialMessages?: ChatMessage[]
    initialCode?: string
    initialTransformationId?: string
}

interface ChatMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    contentType?: 'text' | 'html' | 'markdown'
    timestamp: Date
}

interface TransformationState {
    code: string
    description: string
    transformationId: string
    previewData?: PreviewData
    error?: string
}

interface PreviewData {
    tables: Array<{
        name: string
        columns: Array<{ name: string; type: string }>
        rows: Array<Record<string, any>>
        row_count: number
        preview_row_count: number
    }>
    execution_time_ms: number
}

/** Item shown in the @mention autocomplete dropdown */
interface MentionItem {
    kind: 'source_table' | 'result_table' | 'column'
    label: string      // shown left (table/column name)
    hint: string       // shown right (rows count / column type)
    insertText: string // inserted after @: "tableName" or "tableName.colName"
}

export function TransformDialog({
    open,
    onOpenChange,
    sourceNode,
    sourceNodes,
    onTransform,
    initialMessages,
    initialCode,
    initialTransformationId,
}: TransformDialogProps) {
    console.log('TransformDialog render, open:', open, 'sourceNode:', sourceNode, 'sourceNodes:', sourceNodes)
    console.log('📦 Initial props:', {
        hasInitialMessages: !!initialMessages,
        messagesCount: initialMessages?.length,
        hasInitialCode: !!initialCode,
        codeLength: initialCode?.length,
        initialTransformationId
    })

    // Normalize to array - check length, not just truthiness
    const nodes = (sourceNodes && sourceNodes.length > 0) ? sourceNodes : (sourceNode ? [sourceNode] : [])
    const primaryNode = nodes[0]
    console.log('nodes array:', nodes, 'primaryNode:', primaryNode)

    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
    const [inputValue, setInputValue] = useState('')
    const [isGenerating, setIsGenerating] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [progressSteps, setProgressSteps] = useState<SharedProgressStep[]>([])
    const [progressMeta, setProgressMeta] = useState<SharedProgressMeta>({ current: 0, total: null })
    const [currentTransformation, setCurrentTransformation] = useState<TransformationState | null>(null)
    const [editedCode, setEditedCode] = useState<string | null>(null)
    const [rightPanelTab, setRightPanelTab] = useState<'preview' | 'code'>('preview')
    const [composerTab, setComposerTab] = useState<'message' | 'suggestions'>('message')
    const [composerSuggestionsRefreshKey, setComposerSuggestionsRefreshKey] = useState(0)
    const [composerSuggestionsLoading, setComposerSuggestionsLoading] = useState(false)
    const [selectedSourceTableIndex, setSelectedSourceTableIndex] = useState(0)
    // Autocomplete state
    const [showAutocomplete, setShowAutocomplete] = useState(false)
    const [autocompleteKind, setAutocompleteKind] = useState<'table' | 'column'>('table')
    const [autocompleteTableCtx, setAutocompleteTableCtx] = useState('')
    const [autocompleteSearch, setAutocompleteSearch] = useState('')
    const [autocompleteIndex, setAutocompleteIndex] = useState(0)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const previewLoadedRef = useRef<boolean>(false)
    const autocompleteRef = useRef<HTMLDivElement>(null)

    // Calculate source data info
    const allTables = nodes.flatMap(n => n.content?.tables || [])
    const tableCount = allTables.length
    const totalRows = allTables.reduce((sum, t) => sum + (t.row_count || 0), 0)

    // Result tables from the current transformation preview
    const resultPreviewTables = currentTransformation?.previewData?.tables ?? []

    const chatHistoryForSuggestions = useMemo(
        () => chatMessages.map(msg => ({ role: msg.role, content: msg.content })),
        [chatMessages]
    )

    // Combined pool: source tables + result tables (deduplicated by name)
    const allTablePool = useMemo(() => {
        const pool: Array<{ name: string; rowCount: number; isResult: boolean; columns: Array<{ name: string; type: string }> }> = []
        allTables.forEach(t => pool.push({ name: t.name, rowCount: t.row_count || 0, isResult: false, columns: (t.columns as any[]) || [] }))
        resultPreviewTables.forEach(t => {
            if (!pool.find(p => p.name === t.name))
                pool.push({ name: t.name, rowCount: t.row_count || 0, isResult: true, columns: t.columns || [] })
        })
        return pool
    }, [allTables, resultPreviewTables])

    // Items shown in the autocomplete dropdown
    const autocompleteItems = useMemo((): MentionItem[] => {
        if (autocompleteKind === 'column') {
            const tbl = allTablePool.find(t => t.name === autocompleteTableCtx)
            const filtered = (tbl?.columns ?? []).filter(c =>
                !autocompleteSearch || c.name.toLowerCase().includes(autocompleteSearch.toLowerCase())
            )
            return filtered.map(c => ({
                kind: 'column' as const,
                label: c.name,
                hint: c.type || '',
                insertText: `${autocompleteTableCtx}.${c.name}`,
            }))
        }
        // Table mode
        const filtered = allTablePool.filter(t =>
            !autocompleteSearch || t.name.toLowerCase().includes(autocompleteSearch.toLowerCase())
        )
        return filtered.map(t => ({
            kind: t.isResult ? 'result_table' : 'source_table',
            label: t.name,
            hint: `${t.rowCount.toLocaleString()} rows`,
            insertText: t.name,
        }))
    }, [autocompleteKind, autocompleteTableCtx, autocompleteSearch, allTablePool])

    // Render message content with table references support
    const renderMessageContent = (msg: ChatMessage) => {
        const { content, contentType = 'text' } = msg

        // Handle HTML content (with style isolation via wrapper)
        if (contentType === 'html') {
            return (
                <div
                    className="w-full border rounded bg-white p-3"
                    style={{
                        // Force consistent styling for all child elements
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                        fontSize: '14px',
                        lineHeight: '1.6',
                        color: '#333',
                    }}
                >
                    <style dangerouslySetInnerHTML={{
                        __html: `
                        /* CSS isolation for HTML content - override all inline styles */
                        .html-content-wrapper * {
                            font-family: system-ui, -apple-system, sans-serif !important;
                            color: #333 !important;
                            background: transparent !important;
                        }
                        .html-content-wrapper h1 { 
                            font-size: 16px !important; 
                            margin: 8px 0 !important; 
                            font-weight: 600 !important; 
                        }
                        .html-content-wrapper h2 { 
                            font-size: 14px !important; 
                            margin: 6px 0 !important; 
                            font-weight: 600 !important; 
                        }
                        .html-content-wrapper ul, .html-content-wrapper ol { 
                            margin: 4px 0 !important; 
                            padding-left: 20px !important; 
                        }
                        .html-content-wrapper li { 
                            margin: 2px 0 !important;
                            list-style-position: outside !important;
                        }
                        .html-content-wrapper p { 
                            margin: 4px 0 !important; 
                        }
                    `}} />
                    <div
                        className="html-content-wrapper"
                        dangerouslySetInnerHTML={{ __html: content }}
                    />
                </div>
            )
        }

        // Handle Markdown content
        if (contentType === 'markdown') {
            // Simple markdown parser for common patterns
            const lines = content.split('\n')
            return (
                <div className="space-y-1">
                    {lines.map((line, i) => {
                        // Headers
                        if (line.startsWith('### ')) return <h3 key={i} className="text-sm font-semibold mt-2 mb-1">{line.substring(4)}</h3>
                        if (line.startsWith('## ')) return <h2 key={i} className="text-base font-bold mt-2 mb-1">{line.substring(3)}</h2>
                        if (line.startsWith('# ')) return <h1 key={i} className="text-base font-bold mt-2 mb-1">{line.substring(2)}</h1>

                        // Lists
                        if (line.match(/^[•\-*]\s/)) return <li key={i} className="ml-4 list-disc">{line.substring(2)}</li>
                        if (line.match(/^\d+\.\s/)) return <li key={i} className="ml-4 list-decimal">{line.replace(/^\d+\.\s/, '')}</li>

                        // Bold
                        if (line.includes('**')) {
                            const parts = line.split('**')
                            return <p key={i} className="my-1">{parts.map((part, j) => j % 2 === 1 ? <strong key={j}>{part}</strong> : part)}</p>
                        }

                        // Empty line
                        if (line.trim() === '') return <br key={i} />

                        // Regular text
                        return <p key={i} className="my-1">{line}</p>
                    })}
                </div>
            )
        }

        // Handle text content with @table and @table.column mentions
        const pattern = /@([\w]+(?:\.[\w]+)?)|\[\[([^\]]+)\]\]/g
        const parts: (string | JSX.Element)[] = []
        let lastIndex = 0
        let match: RegExpExecArray | null

        while ((match = pattern.exec(content)) !== null) {
            const mentionText = match[1] || match[2]
            const dotIdx = mentionText.indexOf('.')
            const tName = dotIdx !== -1 ? mentionText.substring(0, dotIdx) : mentionText
            const colName = dotIdx !== -1 ? mentionText.substring(dotIdx + 1) : null
            const srcIdx = allTables.findIndex(t => t.name === tName)
            const isKnown = srcIdx !== -1 || allTablePool.some(t => t.name === tName)

            // Add text before match (preserve newlines)
            if (match.index > lastIndex) {
                const textBefore = content.substring(lastIndex, match.index)
                parts.push(...textBefore.split('\n').flatMap((line, i) =>
                    i === 0 ? [line] : [<br key={`br-${lastIndex}-${i}`} />, line]
                ))
            }

            // Add mention badge
            if (isKnown) {
                if (colName) {
                    // Column mention @tName.colName → muted pill
                    parts.push(
                        <span
                            key={`${match.index}-${mentionText}`}
                            className="inline-flex items-center px-2 py-0.5 mx-0.5 text-xs font-mono rounded bg-muted text-muted-foreground border"
                            title={`Колонка ${colName} таблицы ${tName}`}
                        >
                            {mentionText}
                        </span>
                    )
                } else {
                    // Table mention → blue (source) or green (result) badge
                    parts.push(
                        <button
                            key={`${match.index}-${mentionText}`}
                            onClick={(e) => {
                                e.stopPropagation()
                                if (srcIdx !== -1) setSelectedSourceTableIndex(srcIdx)
                            }}
                            className={cn(
                                'inline-flex items-center px-2 py-0.5 mx-0.5 text-xs font-mono rounded transition-colors',
                                srcIdx !== -1
                                    ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50'
                                    : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 cursor-default'
                            )}
                            title={srcIdx !== -1 ? `Перейти к таблице ${tName}` : `Результирующая таблица ${tName}`}
                        >
                            {tName}
                        </button>
                    )
                }
            } else {
                // Unknown mention, render as is
                parts.push(match[0])
            }

            lastIndex = pattern.lastIndex
        }

        // Add remaining text (preserve newlines)
        if (lastIndex < content.length) {
            const textAfter = content.substring(lastIndex)
            parts.push(...textAfter.split('\n').flatMap((line, i) =>
                i === 0 ? [line] : [<br key={`br-end-${i}`} />, line]
            ))
        }

        return parts.length > 0 ? parts : content
    }

    // Initialize or reset state when dialog opens
    useEffect(() => {
        if (!open) {
            previewLoadedRef.current = false
            setProgressSteps([])
            setProgressMeta({ current: 0, total: null })
            return
        }

        // Always reset isGenerating when dialog opens
        setIsGenerating(false)
        setComposerTab('message')

        if (initialCode && initialTransformationId) {
            // Edit mode: restore data
            console.log('📝 Edit mode initialization:', {
                codeLength: initialCode.length,
                transformationId: initialTransformationId,
                messagesCount: initialMessages?.length || 0
            })
            setChatMessages(initialMessages || [])
            setCurrentTransformation({
                code: initialCode,
                description: 'Existing transformation',
                transformationId: initialTransformationId,
            })
            setEditedCode(null)
            setProgressSteps([])
            setProgressMeta({ current: 0, total: null })
            previewLoadedRef.current = false // Reset flag to trigger preview load
        } else {
            // Create mode: reset
            setChatMessages([])
            setInputValue('')
            setCurrentTransformation(null)
            setEditedCode(null)
            setProgressSteps([])
            setProgressMeta({ current: 0, total: null })
            setRightPanelTab('preview')
            previewLoadedRef.current = false
        }
    }, [open, initialCode, initialTransformationId, initialMessages])

    // Auto-execute initial code to load preview
    useEffect(() => {
        if (!open || !initialCode || !initialTransformationId || !primaryNode) {
            console.log('⏭️ Skipping auto-execute:', {
                open,
                hasInitialCode: !!initialCode,
                hasInitialTransformationId: !!initialTransformationId,
                hasPrimaryNode: !!primaryNode
            })
            return
        }

        // Check if preview is already loaded
        if (previewLoadedRef.current) {
            console.log('✅ Preview already loaded, skipping auto-execute')
            return
        }

        console.log('🔄 Auto-executing initial code for preview...', {
            nodeId: primaryNode.id,
            codeLength: initialCode.length,
            transformationId: initialTransformationId,
            currentTransformationSet: !!currentTransformation
        })

        const loadPreview = async () => {
            setIsGenerating(true)
            try {
                const response = await contentNodesAPI.transformTest(primaryNode.id, {
                    code: initialCode,
                    transformation_id: initialTransformationId,
                    selected_node_ids: nodes.map(n => n.id),
                })

                const result = response.data
                console.log('✅ Preview loaded:', {
                    tables: result.tables?.length,
                    executionTime: result.execution_time_ms
                })

                setCurrentTransformation(prev => {
                    if (!prev) {
                        console.warn('⚠️ No currentTransformation to update, creating new')
                        return {
                            code: initialCode,
                            description: 'Existing transformation',
                            transformationId: initialTransformationId,
                            previewData: {
                                tables: result.tables,
                                execution_time_ms: result.execution_time_ms,
                                row_counts: result.row_counts
                            }
                        }
                    }
                    return {
                        ...prev,
                        previewData: {
                            tables: result.tables,
                            execution_time_ms: result.execution_time_ms,
                            row_counts: result.row_counts
                        }
                    }
                })

                previewLoadedRef.current = true
            } catch (error) {
                console.error('❌ Failed to load initial preview:', error)
            } finally {
                setIsGenerating(false)
            }
        }

        loadPreview()
    }, [open, initialCode, initialTransformationId, primaryNode?.id])

    // После отправки сбрасываем инлайн-height — иначе остаётся высота многострочного ввода
    useEffect(() => {
        const el = textareaRef.current
        if (!el || inputValue !== '') return
        el.style.height = ''
    }, [inputValue])

    // Auto-scroll chat
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [chatMessages, isGenerating, progressSteps.length, progressMeta.current])

    // Close autocomplete on click outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (showAutocomplete &&
                autocompleteRef.current &&
                !autocompleteRef.current.contains(event.target as Node) &&
                textareaRef.current &&
                !textareaRef.current.contains(event.target as Node)) {
                setShowAutocomplete(false)
                setAutocompleteSearch('')
                setAutocompleteIndex(0)
            }
        }

        if (showAutocomplete) {
            document.addEventListener('mousedown', handleClickOutside)
            return () => document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [showAutocomplete])

    // Scroll autocomplete selected item into view
    useEffect(() => {
        if (showAutocomplete && autocompleteRef.current) {
            const selectedElement = autocompleteRef.current.children[autocompleteIndex] as HTMLElement
            if (selectedElement) {
                selectedElement.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
            }
        }
    }, [autocompleteIndex, showAutocomplete])

    console.log('primaryNode check:', primaryNode)
    if (!primaryNode) {
        console.error('❌ primaryNode is null/undefined, returning null')
        return null
    }
    console.log('✅ primaryNode exists, rendering dialog')

    // Handle send message - iterative generation
    const handleSendMessage = async (messageText?: string) => {
        const textToSend = messageText || inputValue.trim()
        if (!textToSend || isGenerating) return

        const userMessage: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'user',
            content: textToSend,
            timestamp: new Date()
        }

        setChatMessages(prev => [...prev, userMessage])
        setInputValue('')
        setIsGenerating(true)
        setProgressSteps([])
        setProgressMeta({ current: 0, total: null })

        try {
            // Build chat history
            const fullChatHistory = [
                ...chatMessages.map(msg => ({
                    role: msg.role,
                    content: msg.content
                })),
                { role: userMessage.role, content: userMessage.content }
            ]

            let data: any = null
            let streamError: string | null = null
            await contentNodesAPI.transformMultiagentStream(
                primaryNode.id,
                {
                    user_prompt: userMessage.content,
                    existing_code: currentTransformation?.code,
                    transformation_id: currentTransformation?.transformationId,
                    chat_history: fullChatHistory,
                    selected_node_ids: nodes.map(n => n.id),
                    preview_only: true,
                },
                {
                    onPlanUpdate: (steps, meta) => {
                        setProgressSteps((prev) => {
                            const next = mergePlanSteps(prev, steps, meta?.completedCount, 'transform')
                            setProgressMeta(metaFromSteps(next))
                            return next
                        })
                    },
                    onProgress: (_agentLabel, task, meta) => {
                        setProgressSteps((prev) => {
                            const next = applyProgressToSteps(prev, task, meta?.stepIndex, 'transform')
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
                        data = result
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
                throw new Error('Пустой результат трансформации')
            }
            setProgressSteps((prev) => {
                const next = markRunningAsCompleted(prev)
                setProgressMeta(metaFromSteps(next))
                return next
            })

            console.log('🤖 AI response received:', data)
            console.log('📄 Code length:', data.code?.length || 0, 'chars')
            console.log('📄 First 100 chars:', data.code?.substring(0, 100) || 'NULL')
            console.log('📊 Preview tables:', data.preview_data?.tables?.length || 0)

            // Check if this is discussion mode (no code generated)
            const isDiscussionMode = data.code === null || data.mode === 'discussion'

            // Add AI response with content type
            const aiMessage: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: data.description || 'Обработка создана',
                contentType: data.content_type || 'text',
                timestamp: new Date()
            }
            setChatMessages(prev => [...prev, aiMessage])

            if (isDiscussionMode) {
                // Discussion mode: just show text response, no code/preview
                console.log('💬 Discussion mode response received')
            } else {
                // Transformation mode: update code and preview
                // Check if execution failed
                const executionError = !data.preview_data
                    ? `Код не выполнился. ${data.validation?.errors?.[0] || 'Проверьте синтаксис.'}`
                    : undefined

                // Update transformation state
                setCurrentTransformation({
                    code: data.code,
                    description: data.description,
                    transformationId: data.transformation_id,
                    previewData: data.preview_data,
                    error: executionError
                })

                if (executionError) {
                    console.error('❌ Execution failed:', executionError)
                }

                // Reset edited code
                setEditedCode(null)

                // Switch to preview tab to show results
                setRightPanelTab('preview')
            }

        } catch (error) {
            console.error('Transform generation failed:', error)
            setProgressSteps((prev) => markLastRunningAsFailed(prev))

            // Extract error message from axios error or generic error
            let errorText = 'Ошибка генерации кода'
            if (error && typeof error === 'object' && 'response' in error) {
                const axiosError = error as any
                errorText = axiosError.response?.data?.detail || axiosError.message || errorText
            } else if (error instanceof Error) {
                errorText = error.message
            }

            const errorMessage: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: `❌ ${errorText}`,
                timestamp: new Date()
            }
            setChatMessages(prev => [...prev, errorMessage])
        } finally {
            setIsGenerating(false)
        }
    }

    // Handle autocomplete selection
    const insertMention = (item: MentionItem) => {
        const textarea = textareaRef.current
        if (!textarea) return

        const cursorPos = textarea.selectionStart
        const textBefore = inputValue.substring(0, cursorPos)
        const textAfter = inputValue.substring(cursorPos)

        const atIdx = textBefore.lastIndexOf('@')
        if (atIdx === -1) return

        const newValue = textBefore.substring(0, atIdx) + `@${item.insertText} ` + textAfter
        setInputValue(newValue)

        setShowAutocomplete(false)
        setAutocompleteSearch('')
        setAutocompleteIndex(0)
        setAutocompleteTableCtx('')
        setAutocompleteKind('table')

        setTimeout(() => {
            textarea.focus()
            const newCursorPos = atIdx + item.insertText.length + 2
            textarea.setSelectionRange(newCursorPos, newCursorPos)
        }, 0)
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        // Autocomplete navigation
        if (showAutocomplete && autocompleteItems.length > 0) {
            if (e.key === 'ArrowDown') {
                e.preventDefault()
                setAutocompleteIndex(prev => (prev + 1) % autocompleteItems.length)
                return
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault()
                setAutocompleteIndex(prev => (prev - 1 + autocompleteItems.length) % autocompleteItems.length)
                return
            }
            if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault()
                if (autocompleteItems[autocompleteIndex]) insertMention(autocompleteItems[autocompleteIndex])
                return
            }
            if (e.key === 'Escape') {
                e.preventDefault()
                setShowAutocomplete(false)
                setAutocompleteSearch('')
                setAutocompleteIndex(0)
                setAutocompleteTableCtx('')
                setAutocompleteKind('table')
                return
            }
        }

        // Normal enter to send
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSendMessage()
        }
    }

    // Auto-resize textarea and handle @-mention autocomplete
    const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const newValue = e.target.value
        setInputValue(newValue)

        const textarea = e.target
        const minH = 56 // ~2 строки text-sm + py-1.5
        textarea.style.height = 'auto'
        textarea.style.height = `${Math.max(minH, Math.min(textarea.scrollHeight, 120))}px`

        const cursorPos = textarea.selectionStart
        const textBeforeCursor = newValue.substring(0, cursorPos)

        // Column mode: @tableName.searchTerm
        const colMatch = textBeforeCursor.match(/@(\w+)\.(\w*)$/)
        // Table mode: @searchTerm (no dot yet)
        const atMatch = !colMatch ? textBeforeCursor.match(/@(\w*)$/) : null

        if (colMatch) {
            const tableName = colMatch[1]
            const colSearch = colMatch[2]
            const knownTable = allTablePool.find(t => t.name === tableName)
            if (knownTable && knownTable.columns.length > 0) {
                setShowAutocomplete(true)
                setAutocompleteKind('column')
                setAutocompleteTableCtx(tableName)
                setAutocompleteSearch(colSearch)
                setAutocompleteIndex(0)
            } else {
                setShowAutocomplete(false)
                setAutocompleteTableCtx('')
                setAutocompleteKind('table')
            }
        } else if (atMatch && allTablePool.length > 0) {
            setShowAutocomplete(true)
            setAutocompleteKind('table')
            setAutocompleteTableCtx('')
            setAutocompleteSearch(atMatch[1])
            setAutocompleteIndex(0)
        } else {
            setShowAutocomplete(false)
            setAutocompleteSearch('')
            setAutocompleteIndex(0)
            setAutocompleteTableCtx('')
            setAutocompleteKind('table')
        }
    }

    // Apply manual code edits
    const handleApplyCode = async () => {
        if (!editedCode || !currentTransformation) return

        setIsGenerating(true)
        try {
            // Test edited code
            const response = await contentNodesAPI.transformTest(primaryNode.id, {
                code: editedCode,
                transformation_id: currentTransformation.transformationId,
                selected_node_ids: nodes.map(n => n.id)
            })

            const result = response.data

            // Check if execution was successful
            if (!result.success) {
                throw new Error(result.error || 'Код не выполнился')
            }

            // Update transformation with tested code
            setCurrentTransformation({
                ...currentTransformation,
                code: editedCode,
                previewData: {
                    tables: result.tables,
                    execution_time_ms: result.execution_time_ms
                },
                error: undefined
            })

            setEditedCode(null)
            setRightPanelTab('preview')
        } catch (error) {
            console.error('Code test failed:', error)

            // Update transformation with error
            setCurrentTransformation({
                ...currentTransformation,
                code: editedCode,
                error: error instanceof Error ? error.message : 'Не удалось выполнить код'
            })

            // Stay on code tab to allow fixing
            setRightPanelTab('code')
        } finally {
            setIsGenerating(false)
        }
    }

    // Save transformation
    const handleSaveToBoard = async () => {
        if (!currentTransformation || isSaving) return

        setIsSaving(true)
        try {
            const code = editedCode || currentTransformation.code
            // Convert ChatMessage to simple format for API
            const historyForAPI = chatMessages.map(msg => ({
                role: msg.role,
                content: msg.content
            }))
            await onTransform(code, currentTransformation.transformationId, currentTransformation.description, historyForAPI)
            onOpenChange(false)
        } catch (error) {
            console.error('Failed to save transformation:', error)
            alert(`Ошибка: ${error instanceof Error ? error.message : 'Не удалось сохранить'}`)
        } finally {
            setIsSaving(false)
        }
    }

    // Render table helper
    const renderTable = (table: PreviewData['tables'][0]) => (
        <div className="border rounded-lg p-3 space-y-3">
            <div className="flex items-center justify-between">
                <div className="font-medium">
                    Таблица: <code className="bg-primary/10 px-1.5 py-0.5 rounded text-sm">{table.name}</code>
                </div>
                <div className="text-xs text-muted-foreground">
                    {table.preview_row_count < table.row_count ? (
                        <span>Показано {table.preview_row_count} из {table.row_count} строк</span>
                    ) : (
                        <span>{table.row_count} строк</span>
                    )}
                </div>
            </div>
            <div className="border rounded overflow-x-auto max-h-[300px] overflow-y-auto">
                <table className="min-w-full text-xs">
                    <thead className="sticky top-0 bg-muted">
                        <tr className="border-b">
                            {table.columns.map((col, idx) => {
                                const colName = col.name
                                return (
                                    <th key={`col-${colName}-${idx}`} className="px-2 py-1.5 text-left font-medium whitespace-nowrap">
                                        {colName}
                                    </th>
                                )
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {table.rows.map((row, rowIdx) => {
                            const colNames = table.columns.map(c => c.name)
                            const rowValues = colNames.map((cn: string) => row?.[cn] ?? '')
                            return (
                                <tr key={`row-${rowIdx}`} className="border-b last:border-0 hover:bg-muted/50">
                                    {rowValues.map((cell, cellIdx) => (
                                        <td key={`cell-${rowIdx}-${cellIdx}`} className="px-2 py-1.5 whitespace-nowrap">
                                            {cell !== null && cell !== undefined ? String(cell) : '-'}
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

    // Render source table helper
    const renderSourceTable = (table: ContentNode['content']['tables'][0], index: number) => (
        <div className="border rounded p-2 space-y-2">
            <div className="text-xs font-medium">
                {table.name} <span className="text-muted-foreground">({table.row_count} строк)</span>
            </div>
            <div className="border rounded overflow-x-auto max-h-[120px] overflow-y-auto">
                <table className="min-w-full text-[10px]">
                    <thead className="sticky top-0 bg-muted">
                        <tr>
                            {table.columns.map((col, idx) => {
                                const colName = col.name
                                return (
                                    <th key={`stat-col-${colName}-${idx}`} className="px-1 py-0.5 text-left font-medium whitespace-nowrap">
                                        {colName}
                                    </th>
                                )
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {table.rows.slice(0, 3).map((row, rowIdx) => {
                            const colNames = table.columns.map(c => c.name)
                            const rowValues = colNames.map((cn: string) => row?.[cn] ?? '')
                            return (
                                <tr key={`stat-row-${rowIdx}`} className="border-t">
                                    {rowValues.map((cell, cellIdx) => (
                                        <td key={`stat-cell-${rowIdx}-${cellIdx}`} className="px-1 py-0.5 whitespace-nowrap">
                                            {cell !== null && cell !== undefined ? String(cell).substring(0, 30) : '-'}
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

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-[1400px] h-[90vh] p-0 flex flex-col nodrag nopan">
                <DialogHeader className="px-6 py-1.5 border-b shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-sm leading-tight">
                        <Code className="h-3.5 w-3.5 text-blue-500" />
                        ИИ-ассистент трансформаций
                    </DialogTitle>
                    <DialogDescription className="text-xs leading-tight mt-0.5">
                        Создайте трансформацию с помощью ИИ или отредактируйте код вручную
                    </DialogDescription>
                </DialogHeader>

                <div className="flex flex-1 min-h-0">
                    {/* Left Panel (40%) - Data + Chat */}
                    <div className="w-[40%] border-r flex flex-col">
                        {/* Source Data Preview */}
                        <div className="flex-1 p-2 border-b overflow-y-auto max-h-[45%]">
                            <div className="text-xs font-medium mb-2">📊 Исходные данные:</div>
                            {allTables.length > 0 ? (
                                <Tabs value={selectedSourceTableIndex.toString()} onValueChange={(v) => setSelectedSourceTableIndex(Number(v))}>
                                    <TabsList className="grid w-full h-7" style={{ gridTemplateColumns: `repeat(${Math.min(allTables.length, 3)}, 1fr)` }}>
                                        {allTables.slice(0, 3).map((table, idx) => (
                                            <TabsTrigger key={`${table.name}-${idx}`} value={idx.toString()} className="text-xs h-6 py-0">
                                                {table.name} ({table.row_count})
                                            </TabsTrigger>
                                        ))}
                                    </TabsList>
                                    <TabsContent value={selectedSourceTableIndex.toString()} className="mt-1">
                                        {renderSourceTable(allTables[selectedSourceTableIndex], selectedSourceTableIndex)}
                                    </TabsContent>
                                </Tabs>
                            ) : (
                                <div className="text-xs text-muted-foreground">Нет данных</div>
                            )}
                        </div>

                        {/* Chat Messages */}
                        <div className="flex items-center justify-between px-3 pt-2 pb-1">
                            <span className="text-xs font-medium text-muted-foreground">💬 Диалог с ИИ</span>
                            {chatMessages.length > 0 && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 px-2 text-xs text-muted-foreground hover:text-destructive"
                                    onClick={() => {
                                        setChatMessages([])
                                        setCurrentTransformation(null)
                                        setEditedCode(null)
                                    }}
                                >
                                    <Trash2 className="w-3 h-3 mr-1" />
                                    Очистить
                                </Button>
                            )}
                        </div>
                        <div
                            className={cn(
                                'flex-1 min-h-0 px-3 pb-3 space-y-2',
                                chatMessages.length === 0 && !isGenerating
                                    ? 'overflow-y-hidden'
                                    : 'overflow-y-auto'
                            )}
                        >
                            {chatMessages.length === 0 ? (
                                <div key="empty-placeholder" className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                                    <Sparkles className="w-10 h-10 mb-3 text-blue-500/30" />
                                    <p className="text-sm">
                                        Опишите какую трансформацию выполнить
                                    </p>
                                    <p className="text-xs mt-2">
                                        Например: "Отфильтровать amount &gt; 100"
                                    </p>
                                    {allTablePool.length > 0 && (
                                        <p className="text-xs mt-2 opacity-70">
                                            @ — таблицы, @{allTablePool[0]?.name}. — колонки
                                        </p>
                                    )}
                                </div>
                            ) : (
                                <div key="messages-container" className="space-y-2">
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
                                                    'max-w-[85%] rounded-lg px-3 py-2 text-sm',
                                                    msg.role === 'user'
                                                        ? 'bg-blue-500 text-white'
                                                        : 'bg-muted'
                                                )}
                                            >
                                                {renderMessageContent(msg)}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                            {isGenerating && (
                                <MultiAgentProgressBlock
                                    runningText="ИИ создаёт код трансформации..."
                                    progressMeta={progressMeta}
                                    progressSteps={progressSteps}
                                    variant="blue"
                                />
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Сообщение / рекомендации — отдельные вкладки; рекомендации грузятся только на вкладке */}
                        <div className="border-t flex flex-col shrink-0 min-h-0">
                            <Tabs
                                value={composerTab}
                                onValueChange={(v) => setComposerTab(v as 'message' | 'suggestions')}
                                className="flex flex-col gap-0"
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
                                                isGenerating ||
                                                isSaving ||
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
                                <TabsContent value="message" className="mt-0 p-2 pt-1 m-0 border-0 focus-visible:outline-none data-[state=inactive]:hidden">
                                    <div className="relative">
                                        {showAutocomplete && autocompleteItems.length > 0 && (
                                            <div
                                                ref={autocompleteRef}
                                                className="absolute bottom-full left-0 right-0 mb-1 bg-popover border rounded-md shadow-lg max-h-[200px] overflow-y-auto z-50"
                                            >
                                                {autocompleteKind === 'column' && (
                                                    <div className="px-3 py-1 text-xs text-muted-foreground border-b bg-muted/50 font-medium select-none">
                                                        Колонки @{autocompleteTableCtx}
                                                    </div>
                                                )}
                                                {autocompleteItems.map((item, idx) => (
                                                    <button
                                                        key={item.insertText}
                                                        onClick={() => insertMention(item)}
                                                        onMouseEnter={() => setAutocompleteIndex(idx)}
                                                        className={cn(
                                                            'w-full px-3 py-2 text-left text-sm flex items-center justify-between hover:bg-accent transition-colors',
                                                            idx === autocompleteIndex && 'bg-accent'
                                                        )}
                                                    >
                                                        <span className="flex items-center gap-1.5 font-mono">
                                                            {item.kind === 'source_table' && <span className="text-blue-500 text-[10px]">📊</span>}
                                                            {item.kind === 'result_table' && <span className="text-green-500 text-[10px] font-bold">→</span>}
                                                            {item.kind === 'column' && <span className="text-muted-foreground text-[10px]">·</span>}
                                                            {item.label}
                                                        </span>
                                                        <span className="text-xs text-muted-foreground">{item.hint}</span>
                                                    </button>
                                                ))}
                                            </div>
                                        )}

                                        <div className="flex gap-2 items-end">
                                            <Textarea
                                                ref={textareaRef}
                                                value={inputValue}
                                                onChange={handleInputChange}
                                                onKeyDown={handleKeyDown}
                                                placeholder={allTablePool.length > 0 ? `Опишите трансформацию (@tableName для таблицы, @tableName.col для колонки)...` : 'Опишите трансформацию...'}
                                                className="min-h-[56px] py-1.5 px-2 resize-none text-sm overflow-hidden"
                                                disabled={isGenerating}
                                                rows={2}
                                            />
                                            <Button
                                                onClick={() => handleSendMessage()}
                                                disabled={!inputValue.trim() || isGenerating}
                                                size="icon"
                                                className="h-[32px] w-[32px] shrink-0 bg-blue-500 hover:bg-blue-600"
                                            >
                                                {isGenerating ? (
                                                    <Loader2 className="w-5 h-5 animate-spin" />
                                                ) : (
                                                    <Send className="w-5 h-5" />
                                                )}
                                            </Button>
                                        </div>
                                    </div>
                                </TabsContent>
                                <TabsContent
                                    value="suggestions"
                                    forceMount
                                    className="mt-0 m-0 p-2 pt-1 flex-none h-fit min-h-0 max-h-[min(36vh,260px)] overflow-y-auto border-0 focus-visible:outline-none data-[state=inactive]:hidden"
                                >
                                    <TransformSuggestionsPanel
                                        contentNodeId={primaryNode.id}
                                        chatHistory={chatHistoryForSuggestions}
                                        currentCode={currentTransformation?.code}
                                        suggestionsTabActive={composerTab === 'suggestions'}
                                        isGenerating={isGenerating}
                                        suggestionsRefreshKey={composerSuggestionsRefreshKey}
                                        onSuggestionsLoadingChange={setComposerSuggestionsLoading}
                                        onSuggestionClick={(prompt) => {
                                            handleSendMessage(prompt)
                                            setComposerTab('message')
                                        }}
                                    />
                                </TabsContent>
                            </Tabs>
                        </div>
                    </div>

                    {/* Right Panel (60%) - Preview & Code */}
                    <div className="w-[60%] flex flex-col">
                        {/* Tabs */}
                        <div className="px-3 pt-2 pb-1 border-b">
                            {currentTransformation?.transformationId && (
                                <div className="text-xs text-muted-foreground mb-1.5">
                                    ID: {currentTransformation.transformationId.slice(0, 8)}...
                                </div>
                            )}
                            <Tabs value={rightPanelTab} onValueChange={(v) => setRightPanelTab(v as 'preview' | 'code')}>
                                <TabsList className="h-8 w-full grid grid-cols-2">
                                    <TabsTrigger value="preview" className="flex items-center gap-1.5 text-xs h-7">
                                        <Eye className="w-3.5 h-3.5" />
                                        Предпросмотр
                                    </TabsTrigger>
                                    <TabsTrigger value="code" className="flex items-center gap-1.5 text-xs h-7">
                                        <Code className="w-3.5 h-3.5" />
                                        Код Python/pandas
                                    </TabsTrigger>
                                </TabsList>
                            </Tabs>
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 p-3 flex flex-col overflow-hidden">
                            {/* Preview Panel */}
                            <div className={cn("flex-1 flex flex-col overflow-hidden", rightPanelTab !== 'preview' && "hidden")}>
                                {currentTransformation?.error ? (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="text-center max-w-md">
                                            <div className="text-destructive text-sm font-medium mb-2">
                                                ❌ Ошибка выполнения
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                {currentTransformation.error}
                                            </div>
                                            <div className="text-xs text-muted-foreground mt-2">
                                                Проверьте код во вкладке "Код Python/pandas"
                                            </div>
                                        </div>
                                    </div>
                                ) : currentTransformation?.previewData ? (
                                    <div className="flex-1 flex flex-col overflow-hidden">
                                        <div className="text-xs text-muted-foreground mb-2">
                                            ⚡ Выполнено за {currentTransformation.previewData?.execution_time_ms || 0}ms
                                        </div>

                                        {/* Tabs for multiple tables */}
                                        {(currentTransformation.previewData?.tables?.length || 0) > 1 ? (
                                            <Tabs defaultValue="0" className="flex-1 flex flex-col overflow-hidden">
                                                <TabsList className="h-8 shrink-0">
                                                    {currentTransformation.previewData?.tables?.map((table, idx) => (
                                                        <TabsTrigger
                                                            key={`preview-tab-${table.name}-${idx}`}
                                                            value={String(idx)}
                                                            className="text-xs h-7 px-2"
                                                        >
                                                            {table.name} <span className="ml-1 text-muted-foreground">({table.row_count})</span>
                                                        </TabsTrigger>
                                                    ))}
                                                </TabsList>
                                                {currentTransformation.previewData?.tables?.map((table, idx) => (
                                                    <TabsContent
                                                        key={`preview-content-${table.name}-${idx}`}
                                                        value={String(idx)}
                                                        className="flex-1 mt-2 overflow-hidden"
                                                    >
                                                        <div className="h-full overflow-y-auto">
                                                            {renderTable(table)}
                                                        </div>
                                                    </TabsContent>
                                                ))}
                                            </Tabs>
                                        ) : currentTransformation.previewData?.tables?.[0] ? (
                                            <div className="flex-1 overflow-y-auto">
                                                {renderTable(currentTransformation.previewData.tables[0])}
                                            </div>
                                        ) : null}
                                    </div>
                                ) : (
                                    <div className="flex-1 flex items-center justify-center text-muted-foreground">
                                        <div className="text-center">
                                            <Eye className="w-12 h-12 mx-auto mb-2 opacity-30" />
                                            <p className="text-sm">Результаты появятся после генерации</p>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Code Panel */}
                            <div className={cn("flex-1 flex flex-col", rightPanelTab !== 'code' && "hidden")}>
                                {editedCode && (
                                    <div className="flex items-center justify-between mb-2 p-2 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-md">
                                        <span className="text-xs text-amber-700 dark:text-amber-400">
                                            ⚠️ Код изменён, нажмите "Применить" для проверки
                                        </span>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={handleApplyCode}
                                            disabled={isGenerating}
                                            className="ml-2 bg-white dark:bg-gray-900"
                                        >
                                            {isGenerating ? (
                                                <><Loader2 className="w-3 h-3 mr-1 animate-spin" />Тестирование...</>
                                            ) : (
                                                <>Применить изменения</>
                                            )}
                                        </Button>
                                    </div>
                                )}
                                {currentTransformation ? (
                                    <div className="flex-1 flex flex-col overflow-hidden">
                                        <div className="text-xs font-medium mb-2">Python/pandas код</div>
                                        <div className="flex-1 border rounded-lg overflow-hidden">
                                            <Editor
                                                height="100%"
                                                language="python"
                                                value={(() => {
                                                    const displayCode = editedCode || currentTransformation.code
                                                    console.log('👁️ CodeEditor rendering:', displayCode ? `${displayCode.length} chars, using ${editedCode ? 'EDITED' : 'CURRENT'}, starts: ${displayCode.substring(0, 80)}` : 'no code')
                                                    return displayCode
                                                })()}
                                                onChange={(value) => setEditedCode(value || null)}
                                                options={{
                                                    minimap: { enabled: false },
                                                    fontSize: 12,
                                                    lineNumbers: 'on',
                                                    scrollBeyondLastLine: false,
                                                }}
                                            />
                                        </div>
                                        {currentTransformation.error && (
                                            <div className="mt-2 p-2 bg-destructive/10 border border-destructive/30 rounded-md">
                                                <div className="text-xs font-medium text-destructive mb-1">
                                                    ❌ Ошибка выполнения:
                                                </div>
                                                <div className="text-xs text-muted-foreground font-mono">
                                                    {currentTransformation.error}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="flex-1 border rounded-lg flex items-center justify-center text-muted-foreground">
                                        <div className="text-center">
                                            <Code className="w-12 h-12 mx-auto mb-2 opacity-30" />
                                            <p className="text-sm">Код появится после генерации</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                <DialogFooter className="px-6 py-1.5 border-t shrink-0">
                    <div className="flex items-center justify-between w-full">
                        <div className="text-xs text-muted-foreground">
                            {currentTransformation && (
                                <>📝 {currentTransformation.description}</>
                            )}
                        </div>
                        <div className="flex gap-2">
                            <Button
                                variant="outline"
                                onClick={() => onOpenChange(false)}
                            >
                                Отмена
                            </Button>
                            <Button
                                onClick={handleSaveToBoard}
                                disabled={!currentTransformation || isSaving || !!currentTransformation?.error}
                                className="bg-blue-500 hover:bg-blue-600"
                                title={currentTransformation?.error ? 'Исправьте ошибки перед сохранением' : editedCode ? 'Сохранит отредактированный код' : undefined}
                            >
                                {isSaving ? (
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <Save className="w-4 h-4 mr-2" />
                                )}
                                {isSaving ? 'Сохранение...' : 'Сохранить трансформацию'}
                            </Button>
                        </div>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
