import { useEffect, useRef, useState } from 'react'
import { Send, Trash2, Sparkles, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { MultiAgentProgressBlock } from '@/components/shared/MultiAgentProgressBlock'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { runPlaygroundStream, type PlaygroundChatMessage } from '@/services/adminSystemLlMApi'
import {
    type ProgressStep as SharedProgressStep,
    type ProgressMeta as SharedProgressMeta,
    mergePlanSteps,
    applyProgressToSteps,
    updateMetaFromPlanEvent,
    updateMetaFromProgressEvent,
    markRunningAsCompleted,
    markLastRunningAsFailed,
    finalizeMeta,
} from '@/lib/multiAgentProgress'

type PlaygroundMessage = {
    id: string
    role: 'user' | 'assistant'
    content: string
    raw?: Record<string, unknown>
}

/** Итоговый ответ ИИ (narrative). План и время — в «Подробности (JSON)». */
function formatPlaygroundResult(result: Record<string, unknown>): string {
    const status = result.status as string
    if (status === 'error') {
        return `Ошибка: ${result.error ?? 'Неизвестная ошибка'}`
    }
    const results = result.results as Record<string, { narrative?: { text?: string } | string }> | undefined
    if (results) {
        let narrativeText = (results.reporter?.narrative as { text?: string } | undefined)?.text
        if (!narrativeText && typeof results.reporter?.narrative === 'string') narrativeText = results.reporter.narrative
        if (!narrativeText) {
            for (const v of Object.values(results)) {
                if (v && typeof v === 'object' && v.narrative) {
                    narrativeText =
                        typeof v.narrative === 'string' ? v.narrative : (v.narrative as { text?: string }).text
                    if (narrativeText) break
                }
            }
        }
        if (narrativeText?.trim()) return narrativeText.trim()
    }
    return 'Готово.'
}

export function MultiAgentPlaygroundPanel() {
    const [playgroundMessages, setPlaygroundMessages] = useState<PlaygroundMessage[]>([])
    const [playgroundInput, setPlaygroundInput] = useState('')
    const [playgroundRunning, setPlaygroundRunning] = useState(false)
    const [playgroundProgressSteps, setPlaygroundProgressSteps] = useState<SharedProgressStep[]>([])
    const [playgroundProgressMeta, setPlaygroundProgressMeta] = useState<SharedProgressMeta>({
        current: 0,
        total: null,
    })
    const messagesContainerRef = useRef<HTMLDivElement>(null)
    const playgroundEndRef = useRef<HTMLDivElement>(null)
    const shouldAutoScrollRef = useRef(true)

    const handleRunPlayground = async () => {
        const text = playgroundInput.trim()
        if (!text || playgroundRunning) return

        const userMsg: PlaygroundMessage = { id: `u-${Date.now()}`, role: 'user', content: text }
        const historyForRequest: PlaygroundChatMessage[] = [...playgroundMessages, userMsg]
            .map((m) => ({
                role: m.role,
                content: m.content,
            }))
            .slice(-10)

        setPlaygroundMessages((prev) => [...prev, userMsg])
        setPlaygroundInput('')
        setPlaygroundRunning(true)
        setPlaygroundProgressSteps([])
        setPlaygroundProgressMeta({ current: 0, total: null })
        try {
            let finalResult: Record<string, unknown> | null = null
            let streamError: string | null = null

            await runPlaygroundStream(text, historyForRequest, {
                onPlanUpdate: (steps, meta) => {
                    setPlaygroundProgressSteps((prev) =>
                        mergePlanSteps(prev, steps, meta?.completedCount, 'playground')
                    )
                    setPlaygroundProgressMeta((prev) =>
                        updateMetaFromPlanEvent(prev, steps.length, meta?.completedCount)
                    )
                },
                onProgress: (_agentLabel, task, meta) => {
                    setPlaygroundProgressSteps((prev) =>
                        applyProgressToSteps(prev, task, meta?.stepIndex, 'playground')
                    )
                    setPlaygroundProgressMeta((prev) =>
                        updateMetaFromProgressEvent(prev, meta?.stepIndex, meta?.totalSteps)
                    )
                },
                onResult: (result) => {
                    finalResult = result
                },
                onError: (errorText) => {
                    streamError = errorText
                },
            })

            if (streamError) {
                throw new Error(streamError)
            }
            if (!finalResult) {
                throw new Error('Playground не вернул финальный результат')
            }
            setPlaygroundProgressSteps((prev) => markRunningAsCompleted(prev))
            setPlaygroundProgressMeta((prev) => finalizeMeta(prev, playgroundProgressSteps.length))

            const displayText = formatPlaygroundResult(finalResult)
            const assistantMsg: PlaygroundMessage = {
                id: `a-${Date.now()}`,
                role: 'assistant',
                content: displayText,
                raw: finalResult,
            }
            setPlaygroundMessages((prev) => [...prev, assistantMsg])
        } catch (e: unknown) {
            const errText = e instanceof Error ? e.message : 'Запуск не удался'
            setPlaygroundProgressSteps((prev) => markLastRunningAsFailed(prev))
            setPlaygroundMessages((prev) => [
                ...prev,
                { id: `a-${Date.now()}`, role: 'assistant', content: `Ошибка: ${errText}` },
            ])
        } finally {
            setPlaygroundRunning(false)
        }
    }

    const handleClearPlayground = () => setPlaygroundMessages([])

    const updateAutoScrollState = () => {
        const container = messagesContainerRef.current
        if (!container) return
        const distanceFromBottom =
            container.scrollHeight - container.scrollTop - container.clientHeight
        shouldAutoScrollRef.current = distanceFromBottom < 120
    }

    useEffect(() => {
        const container = messagesContainerRef.current
        if (!container) return
        if (!playgroundRunning && !shouldAutoScrollRef.current) return
        container.scrollTop = container.scrollHeight
        playgroundEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [playgroundMessages.length, playgroundRunning, playgroundProgressSteps.length, playgroundProgressMeta.current])

    return (
        <div className="space-y-4">
            <div className="space-y-1">
                <h2 className="text-lg font-semibold">Playground (мультиагент)</h2>
                <p className="text-sm text-muted-foreground">
                    Чат с мультиагентным пайплайном. Используется модель по умолчанию и привязки агентов из
                    раздела «Настройки LLM».
                </p>
            </div>

            <div className="rounded-lg border border-border bg-card p-4 flex flex-col min-h-[420px]">
                <div className="flex items-center justify-between pb-2 border-b border-border">
                    <p className="text-sm text-muted-foreground">Запросы к оркестратору (тестовая доска).</p>
                    {playgroundMessages.length > 0 && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleClearPlayground}
                            title="Очистить историю"
                            className="h-8 w-8"
                        >
                            <Trash2 className="w-4 h-4" />
                        </Button>
                    )}
                </div>
                <div
                    ref={messagesContainerRef}
                    onScroll={updateAutoScrollState}
                    className="flex-1 overflow-y-auto py-3 space-y-2 min-h-[200px]"
                >
                    {playgroundMessages.length === 0 && !playgroundRunning ? (
                        <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                            <Sparkles className="w-10 h-10 mb-3 text-primary/40" />
                            <p className="text-sm">
                                Введите запрос и нажмите Отправить — мультиагент выполнит план и вернёт ответ.
                            </p>
                        </div>
                    ) : (
                        playgroundMessages.map((msg) => (
                            <div
                                key={msg.id}
                                className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}
                            >
                                <div
                                    className={cn(
                                        'max-w-[90%] rounded-lg px-3 py-2 text-sm',
                                        msg.role === 'user'
                                            ? 'bg-primary/15 text-foreground'
                                            : 'bg-muted text-foreground'
                                    )}
                                >
                                    {msg.role === 'assistant' ? (
                                        <div className="prose prose-sm dark:prose-invert max-w-none break-words [&_pre]:text-xs [&_pre]:py-1.5 [&_pre]:px-2 [&_ul]:my-1 [&_ol]:my-1 [&_p]:my-0.5">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                                        </div>
                                    ) : (
                                        <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                                    )}
                                    {msg.raw != null && (
                                        <details className="mt-2 pt-2 border-t border-border/30">
                                            <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                                                Подробности (JSON)
                                            </summary>
                                            <pre className="mt-1 text-xs overflow-auto max-h-[200px] whitespace-pre-wrap break-words">
                                                {JSON.stringify(msg.raw, null, 2)}
                                            </pre>
                                        </details>
                                    )}
                                </div>
                            </div>
                        ))
                    )}
                    {playgroundRunning && (
                        <div className="flex justify-start">
                            <div className="max-w-[90%]">
                                <MultiAgentProgressBlock
                                    runningText="Мультиагент выполняется..."
                                    progressMeta={playgroundProgressMeta}
                                    progressSteps={playgroundProgressSteps}
                                    variant="primary"
                                />
                            </div>
                        </div>
                    )}
                    <div ref={playgroundEndRef} />
                </div>
                <div className="pt-2 border-t border-border">
                    <div className="flex gap-2">
                        <Textarea
                            value={playgroundInput}
                            onChange={(e) => setPlaygroundInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault()
                                    void handleRunPlayground()
                                }
                            }}
                            placeholder="Например: проанализируй данные и предложи визуализацию..."
                            className="min-h-[48px] max-h-[120px] resize-none"
                            disabled={playgroundRunning}
                        />
                        <Button
                            onClick={() => void handleRunPlayground()}
                            disabled={!playgroundInput.trim() || playgroundRunning}
                            size="icon"
                            className="h-[48px] w-[48px] shrink-0"
                        >
                            {playgroundRunning ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <Send className="w-5 h-5" />
                            )}
                        </Button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1.5">
                        Enter — отправить, Shift+Enter — новая строка
                    </p>
                </div>
            </div>
        </div>
    )
}
