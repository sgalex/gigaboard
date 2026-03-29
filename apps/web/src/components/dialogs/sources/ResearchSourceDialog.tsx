/**
 * Research Source Dialog — AI Deep Research с чатом слева и превью справа.
 * См. docs/AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md
 */
import { useState, useRef, useEffect } from 'react'
import { Search, Send, Loader2, ExternalLink, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { SourceType, type SourceNode } from '@/types'
import { notify } from '@/store/notificationStore'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'
import { BaseSourceDialog } from './BaseSourceDialog'
import { researchAPI } from '@/services/api'
import type { ResearchChatResponse, ResearchChatMessage } from '@/types'
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

const EMPTY_PLACEHOLDER = 'Данные появятся по результатам исследования.'

const NARRATIVE_PREVIEW_LEN = 500

/** Последние N реплик для контекста оркестратора (как в ИИ-ассистенте). */
const AGENT_CHAT_HISTORY_LIMIT = 20

function buildAgentChatHistory(
    messages: { role: string; content: string }[]
): { role: string; content: string }[] {
    return messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content }))
        .slice(-AGENT_CHAT_HISTORY_LIMIT)
}

function parseConversationHistory(raw: unknown): ResearchChatMessage[] {
    if (!Array.isArray(raw)) return []
    const out: ResearchChatMessage[] = []
    for (const m of raw) {
        if (
            m &&
            typeof m === 'object' &&
            (m as ResearchChatMessage).role !== undefined &&
            ((m as ResearchChatMessage).role === 'user' ||
                (m as ResearchChatMessage).role === 'assistant') &&
            typeof (m as ResearchChatMessage).content === 'string'
        ) {
            out.push({
                role: (m as ResearchChatMessage).role,
                content: (m as ResearchChatMessage).content,
            })
        }
    }
    return out
}

function hydrateResearchResultFromNode(source: SourceNode): ResearchChatResponse | null {
    const text = source.content?.text ?? ''
    const tablesRaw = source.content?.tables ?? []
    const hasText = typeof text === 'string' && text.trim().length > 0
    if (!hasText && tablesRaw.length === 0) return null
    return {
        narrative: text || '',
        tables: tablesRaw.map((t) => ({
            name: t.name,
            columns: t.columns ?? [],
            rows: t.rows ?? [],
        })),
        sources: [],
        session_id: '',
    }
}

export function ResearchSourceDialog({
    open,
    onOpenChange,
    initialPosition,
    existingSource,
    mode = 'create',
}: SourceDialogProps) {
    const isEditMode = mode === 'edit' && !!existingSource
    const [inputValue, setInputValue] = useState('')
    const [messages, setMessages] = useState<ResearchChatMessage[]>([])
    const [sessionId, setSessionId] = useState<string | null>(null)
    const [researchResult, setResearchResult] = useState<ResearchChatResponse | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [progressSteps, setProgressSteps] = useState<SharedProgressStep[]>([])
    const [progressMeta, setProgressMeta] = useState<SharedProgressMeta>({ current: 0, total: null })
    const [narrativeExpanded, setNarrativeExpanded] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    const { isLoading: isSaving, create, update } = useSourceDialog({
        sourceType: SourceType.RESEARCH,
        onClose: () => {
            if (!isEditMode) {
                setMessages([])
                setSessionId(null)
                setResearchResult(null)
                setInputValue('')
                setProgressSteps([])
                setProgressMeta({ current: 0, total: null })
                setNarrativeExpanded(false)
            }
            onOpenChange(false)
        },
        position: initialPosition,
    })

    useEffect(() => {
        if (!open || !isEditMode || !existingSource) return
        const cfg = existingSource.config || {}
        let msgs = parseConversationHistory(cfg.conversation_history)
        if (msgs.length === 0 && typeof cfg.initial_prompt === 'string' && cfg.initial_prompt.trim()) {
            msgs = [{ role: 'user', content: cfg.initial_prompt.trim() }]
        }
        setMessages(msgs)
        setSessionId(null)
        setResearchResult(hydrateResearchResultFromNode(existingSource))
        setInputValue('')
        setProgressSteps([])
        setProgressMeta({ current: 0, total: null })
        setNarrativeExpanded(false)
    }, [open, isEditMode, existingSource])

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, researchResult, isLoading, progressSteps.length, progressMeta.current])

    const handleSend = async () => {
        const message = inputValue.trim()
        if (!message || isLoading) return

        setInputValue('')
        setMessages((prev) => [...prev, { role: 'user', content: message }])
        setIsLoading(true)
        setResearchResult(null)
        setProgressSteps([])
        setProgressMeta({ current: 0, total: null })

        try {
            const chatHistoryForAgent = buildAgentChatHistory(
                messages.map((m) => ({ role: m.role, content: m.content }))
            )
            let data: ResearchChatResponse | null = null
            let streamError: string | null = null

            await researchAPI.chatStream(
                {
                    message,
                    session_id: sessionId ?? undefined,
                    chat_history: chatHistoryForAgent.length ? chatHistoryForAgent : undefined,
                },
                {
                    onPlanUpdate: (steps, meta) => {
                        setProgressSteps((prev) => {
                            const next = mergePlanSteps(prev, steps, meta?.completedCount, 'research')
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
                                'research'
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
                        data = result as ResearchChatResponse
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
                throw new Error('Пустой ответ исследования')
            }

            setProgressSteps((prev) => {
                const next = markRunningAsCompleted(prev)
                setProgressMeta(metaFromSteps(next))
                return next
            })

            setSessionId(data.session_id)
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: data.narrative || 'Нет текстового ответа.' },
            ])
            setResearchResult(data)
        } catch (err: any) {
            setProgressSteps((prev) => markLastRunningAsFailed(prev))
            const detail =
                err.response?.data?.detail || err.message || 'Ошибка исследования'
            notify.error(detail)
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: `Ошибка: ${detail}` },
            ])
        } finally {
            setIsLoading(false)
        }
    }

    const handleClearChatHistory = () => {
        if (isLoading || isSaving) return
        setMessages([])
        setSessionId(null)
        setResearchResult(null)
        setProgressSteps([])
        setProgressMeta({ current: 0, total: null })
        setNarrativeExpanded(false)
    }

    const canClearChatHistory =
        messages.length > 0 && !isLoading && !isSaving

    const buildContentDataPayload = () => {
        if (!researchResult) return undefined
        const hasNarrative =
            typeof researchResult.narrative === 'string' && researchResult.narrative.trim().length > 0
        const hasTables = (researchResult.tables?.length ?? 0) > 0
        if (!hasNarrative && !hasTables) return undefined
        return {
            text: researchResult.narrative ?? '',
            tables: (researchResult.tables ?? []).map((t) => ({
                name: t.name ?? 'table',
                columns: t.columns ?? [],
                rows: t.rows ?? [],
                row_count: (t.rows ?? []).length,
                column_count: (t.columns ?? []).length,
            })),
        }
    }

    const handleSaveSource = async () => {
        const firstUser = messages.find((m) => m.role === 'user')
        const initialPrompt =
            firstUser?.content?.trim() ||
            (typeof existingSource?.config?.initial_prompt === 'string'
                ? existingSource.config.initial_prompt.trim()
                : '') ||
            'Исследование'
        const name =
            initialPrompt.slice(0, 50) + (initialPrompt.length > 50 ? '...' : '')
        const contentData = buildContentDataPayload()

        const configPayload = {
            initial_prompt: initialPrompt,
            conversation_history: messages,
            context: (existingSource?.config as Record<string, unknown> | undefined)?.context ?? {},
        }

        if (isEditMode && existingSource) {
            const metaName =
                existingSource.metadata?.name ||
                (existingSource as { node_metadata?: { name?: string } }).node_metadata?.name ||
                name ||
                'Поиск с ИИ'
            await update(
                existingSource.id,
                configPayload,
                { ...existingSource.metadata, name: metaName },
                contentData
            )
            return
        }

        await create(configPayload, { name: name || 'Поиск с ИИ' }, contentData)
    }

    const narrativeText = researchResult?.narrative ?? ''
    const showExpandNarrative = narrativeText.length > NARRATIVE_PREVIEW_LEN
    const displayNarrative = narrativeExpanded
        ? narrativeText
        : narrativeText.slice(0, NARRATIVE_PREVIEW_LEN) + (narrativeText.length > NARRATIVE_PREVIEW_LEN ? '…' : '')

    const tables = researchResult?.tables ?? []
    const sources = researchResult?.sources ?? []
    const chatNeedsMessageScroll = messages.length > 0 || isLoading

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Поиск с ИИ"
            description="Запрос к мультиагенту: веб-поиск и структурирование данных"
            icon={<Search className="h-5 w-5 text-pink-500" />}
            isLoading={isSaving}
            isValid
            onSubmit={() => void handleSaveSource()}
            submitLabel={isEditMode ? 'Сохранить' : 'Создать источник'}
            className="w-[calc(100vw-2rem)] max-w-[calc(100vw-2rem)] h-[calc(100vh-2rem)]"
            contentClassName="overflow-hidden !py-0 min-h-0"
        >
            <div className="flex flex-1 min-h-0">
                {/* Левая панель (40%) — чат */}
                <div className="w-[40%] border-r border-border flex flex-col min-h-0">
                    <div className="px-3 py-1.5 bg-muted/40 text-xs text-muted-foreground border-b border-border shrink-0 flex items-center justify-between gap-2">
                        <span>Задайте запрос — агенты найдут и структурируют данные</span>
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
                    <div
                        className={cn(
                            'flex-1 min-h-0 px-3 pb-3 pt-2 flex flex-col',
                            chatNeedsMessageScroll
                                ? 'overflow-y-auto space-y-2'
                                : 'overflow-hidden justify-center py-4'
                        )}
                    >
                        {!chatNeedsMessageScroll ? (
                            <div className="flex flex-col items-center justify-center text-center text-muted-foreground text-sm shrink-0 px-2">
                                <Search className="w-10 h-10 mb-3 text-pink-500/50" />
                                <p>Напишите, какие данные нужно найти.</p>
                                <p className="mt-1 text-xs">
                                    Например: статистика продаж электромобилей по странам за 2024
                                </p>
                            </div>
                        ) : (
                            <>
                                {messages.map((msg, idx) => (
                                    <div
                                        key={idx}
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
                                            {msg.role === 'assistant' ? (
                                                <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0">
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                        {msg.content}
                                                    </ReactMarkdown>
                                                </div>
                                            ) : (
                                                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                                            )}
                                        </div>
                                    </div>
                                ))}
                                {isLoading && (
                                    <MultiAgentProgressBlock
                                        runningText="Мультиагент выполняет исследование..."
                                        progressMeta={progressMeta}
                                        progressSteps={progressSteps}
                                        variant="primary"
                                    />
                                )}
                                <div ref={messagesEndRef} />
                            </>
                        )}
                    </div>
                        <div className="p-2 border-t border-border shrink-0">
                            <div className="flex gap-2">
                                <Textarea
                                    value={inputValue}
                                    onChange={(e) => setInputValue(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter' && !e.shiftKey) {
                                            e.preventDefault()
                                            handleSend()
                                        }
                                    }}
                                    placeholder="Опишите, какие данные найти..."
                                    className="min-h-[44px] max-h-[100px] resize-none"
                                    disabled={isLoading}
                                />
                                <Button
                                    type="button"
                                    size="icon"
                                    className="h-[44px] w-[44px] shrink-0"
                                    onClick={handleSend}
                                    disabled={!inputValue.trim() || isLoading}
                                >
                                    {isLoading ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Send className="w-4 h-4" />
                                    )}
                                </Button>
                            </div>
                        </div>
                    </div>

                {/* Правая панель (60%) — превью результата */}
                <div className="w-[60%] flex flex-col min-h-0 overflow-hidden">
                        <div className="px-3 py-2 bg-muted/40 text-xs text-muted-foreground border-b border-border shrink-0">
                            Результат исследования
                        </div>
                        <div className="flex-1 overflow-y-auto p-3 space-y-4 min-h-0">
                            {!narrativeText && tables.length === 0 && sources.length === 0 ? (
                                <p className="text-sm text-muted-foreground">{EMPTY_PLACEHOLDER}</p>
                            ) : (
                                <>
                                    {narrativeText ? (
                                        <section>
                                            <h4 className="text-xs font-medium text-muted-foreground mb-1">Текст</h4>
                                            <div className="text-sm rounded-md bg-muted/50 p-3 prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0">
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                    {displayNarrative}
                                                </ReactMarkdown>
                                                {showExpandNarrative && (
                                                    <Button
                                                        variant="link"
                                                        className="p-0 h-auto text-xs mt-1"
                                                        onClick={() => setNarrativeExpanded((v) => !v)}
                                                    >
                                                        {narrativeExpanded ? 'Свернуть' : 'Показать полностью'}
                                                    </Button>
                                                )}
                                            </div>
                                        </section>
                                    ) : null}

                                    {tables.length > 0 ? (
                                        <section>
                                            <h4 className="text-xs font-medium text-muted-foreground mb-1">Таблицы</h4>
                                            <Tabs defaultValue={tables[0]?.name ?? '0'} className="w-full">
                                                <TabsList className="w-full flex-wrap h-auto gap-1">
                                                    {tables.map((t, i) => (
                                                        <TabsTrigger key={i} value={t.name ?? String(i)}>
                                                            {t.name || `Таблица ${i + 1}`}
                                                        </TabsTrigger>
                                                    ))}
                                                </TabsList>
                                                {tables.map((t, i) => (
                                                    <TabsContent key={i} value={t.name ?? String(i)} className="mt-2">
                                                        <div className="rounded border overflow-x-auto">
                                                            <table className="w-full text-xs">
                                                                <thead>
                                                                    <tr className="border-b bg-muted/50">
                                                                        {(t.columns ?? []).map((col: { name: string }, j: number) => (
                                                                            <th key={j} className="px-2 py-1.5 text-left font-medium">
                                                                                {col.name}
                                                                            </th>
                                                                        ))}
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    {(t.rows ?? []).slice(0, 30).map((row: Record<string, unknown>, ri: number) => (
                                                                        <tr key={ri} className="border-b border-border/50">
                                                                            {(t.columns ?? []).map((col: { name: string }, ci: number) => (
                                                                                <td key={ci} className="px-2 py-1">
                                                                                    {String(row[col.name] ?? '')}
                                                                                </td>
                                                                            ))}
                                                                        </tr>
                                                                    ))}
                                                                </tbody>
                                                            </table>
                                                            {(t.rows?.length ?? 0) > 30 && (
                                                                <p className="text-xs text-muted-foreground px-2 py-1">
                                                                    Показано 30 из {t.rows?.length} строк
                                                                </p>
                                                            )}
                                                        </div>
                                                    </TabsContent>
                                                ))}
                                            </Tabs>
                                        </section>
                                    ) : null}

                                    {sources.length > 0 ? (
                                        <section>
                                            <h4 className="text-xs font-medium text-muted-foreground mb-1">Источники</h4>
                                            <ul className="space-y-1 text-sm">
                                                {sources.map((s, i) => (
                                                    <li key={i}>
                                                        <a
                                                            href={s.url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="flex items-center gap-1 text-primary hover:underline"
                                                        >
                                                            <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                                                            {s.title || s.url}
                                                        </a>
                                                    </li>
                                                ))}
                                            </ul>
                                        </section>
                                    ) : null}
                                </>
                            )}
                        </div>
                    </div>
            </div>
        </BaseSourceDialog>
    )
}
