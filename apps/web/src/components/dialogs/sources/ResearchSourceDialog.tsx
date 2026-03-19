/**
 * Research Source Dialog — AI Deep Research с чатом слева и превью справа.
 * См. docs/AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md
 */
import { useState, useRef, useEffect } from 'react'
import { Search, Send, Loader2, ExternalLink } from 'lucide-react'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'
import { researchAPI } from '@/services/api'
import type { ResearchChatResponse, ResearchChatMessage } from '@/types'
import { cn } from '@/lib/utils'

const EMPTY_PLACEHOLDER = 'Данные появятся по результатам исследования.'

const NARRATIVE_PREVIEW_LEN = 500

export function ResearchSourceDialog({ open, onOpenChange, initialPosition }: SourceDialogProps) {
    const [inputValue, setInputValue] = useState('')
    const [messages, setMessages] = useState<ResearchChatMessage[]>([])
    const [sessionId, setSessionId] = useState<string | null>(null)
    const [researchResult, setResearchResult] = useState<ResearchChatResponse | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    const { isLoading: isCreating, create } = useSourceDialog({
        sourceType: SourceType.RESEARCH,
        onClose: () => {
            setMessages([])
            setSessionId(null)
            setResearchResult(null)
            setInputValue('')
            onOpenChange(false)
        },
        position: initialPosition,
    })

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, researchResult])

    const handleSend = async () => {
        const message = inputValue.trim()
        if (!message || isLoading) return

        setInputValue('')
        setMessages((prev) => [...prev, { role: 'user', content: message }])
        setIsLoading(true)
        setResearchResult(null)

        try {
            const chatHistory = messages.map((m) => ({ role: m.role, content: m.content }))
            const res = await researchAPI.chat({
                message,
                session_id: sessionId ?? undefined,
                chat_history: chatHistory.length ? chatHistory : undefined,
            })
            const data = res.data

            setSessionId(data.session_id)
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: data.narrative || 'Нет текстового ответа.' },
            ])
            setResearchResult(data)
        } catch (err: any) {
            const detail = err.response?.data?.detail || err.message || 'Ошибка исследования'
            notify.error(detail)
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: `Ошибка: ${detail}` },
            ])
        } finally {
            setIsLoading(false)
        }
    }

    const handleCreateSource = async () => {
        const firstUser = messages.find((m) => m.role === 'user')
        const initialPrompt = firstUser?.content?.trim() || 'Исследование'
        const name = initialPrompt.slice(0, 50) + (initialPrompt.length > 50 ? '...' : '')

        // Передаём уже полученный результат (текст + таблицы), чтобы в источнике сразу был контент
        const contentData =
            researchResult &&
            (researchResult.narrative || (researchResult.tables && researchResult.tables.length > 0))
                ? {
                      text: researchResult.narrative ?? '',
                      tables: (researchResult.tables ?? []).map((t) => ({
                          name: t.name ?? 'table',
                          columns: t.columns ?? [],
                          rows: t.rows ?? [],
                          row_count: (t.rows ?? []).length,
                          column_count: (t.columns ?? []).length,
                      })),
                  }
                : undefined

        await create(
            {
                initial_prompt: initialPrompt,
                conversation_history: messages,
                context: {},
            },
            { name: name || 'AI Research' },
            contentData
        )
    }

    const narrativeText = researchResult?.narrative ?? ''
    const showExpandNarrative = narrativeText.length > NARRATIVE_PREVIEW_LEN
    const [narrativeExpanded, setNarrativeExpanded] = useState(false)
    const displayNarrative = narrativeExpanded
        ? narrativeText
        : narrativeText.slice(0, NARRATIVE_PREVIEW_LEN) + (narrativeText.length > NARRATIVE_PREVIEW_LEN ? '…' : '')

    const tables = researchResult?.tables ?? []
    const sources = researchResult?.sources ?? []

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-5xl max-h-[90vh] flex flex-col p-0 gap-0">
                <DialogHeader className="px-4 py-3 border-b shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-base">
                        <Search className="h-5 w-5 text-pink-500" />
                        AI Research
                    </DialogTitle>
                </DialogHeader>

                <div className="flex-1 grid grid-cols-1 md:grid-cols-[1fr_1fr] min-h-0">
                    {/* Левая колонка — чат */}
                    <div className="flex flex-col border-r border-border min-h-[320px]">
                        <div className="px-3 py-2 bg-muted/40 text-xs text-muted-foreground border-b border-border">
                            Задайте запрос — агенты найдут и структурируют данные
                        </div>
                        <div className="flex-1 overflow-y-auto p-2 space-y-2">
                            {messages.length === 0 && !isLoading ? (
                                <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground text-sm">
                                    <Search className="w-10 h-10 mb-3 text-pink-500/50" />
                                    <p>Напишите, какие данные нужно найти.</p>
                                    <p className="mt-1 text-xs">Например: статистика продаж электромобилей по странам за 2024</p>
                                </div>
                            ) : (
                                messages.map((msg, idx) => (
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
                                ))
                            )}
                            {isLoading && (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Запускаю исследование…
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>
                        <div className="p-2 border-t border-border">
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

                    {/* Правая колонка — превью результата */}
                    <div className="flex flex-col min-h-[320px] overflow-hidden">
                        <div className="px-3 py-2 bg-muted/40 text-xs text-muted-foreground border-b border-border">
                            Результат исследования
                        </div>
                        <div className="flex-1 overflow-y-auto p-3 space-y-4">
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

                <DialogFooter className="px-4 py-3 border-t shrink-0">
                    <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isCreating}>
                        Отмена
                    </Button>
                    <Button onClick={handleCreateSource} disabled={isCreating}>
                        {isCreating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Search className="w-4 h-4 mr-2" />}
                        Создать источник
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
