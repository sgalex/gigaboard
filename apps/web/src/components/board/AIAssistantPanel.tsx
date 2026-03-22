/**
 * AI Assistant Panel - чат-панель для общения с ИИ-ассистентом
 * См. docs/AI_ASSISTANT.md
 */
import { useState, useRef, useEffect } from 'react'
import { Send, Trash2, Sparkles, Loader2 } from 'lucide-react'
import { useAIAssistantStore } from '@/store/aiAssistantStore'
import { useAuthStore } from '@/store/authStore'
import { socketService } from '@/services/socket'
import { useBoardStore } from '@/store/boardStore'
import { useFilterStore } from '@/store/filterStore'
import { useAIStreaming } from '@/hooks/useAIStreaming'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { MultiAgentProgressBlock } from '@/components/shared/MultiAgentProgressBlock'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { MessageRole, AIContextUsed } from '@/types'
import type { FilterExpression } from '@/types/crossFilter'

interface AIAssistantPanelProps {
    contextId: string
    scope?: 'board' | 'dashboard'
    showHeader?: boolean
}

export function AIAssistantPanel({ contextId, scope = 'board', showHeader = true }: AIAssistantPanelProps) {
    const {
        messages,
        isLoading,
        isStreaming,
        currentStreamMessage,
        progressSteps,
        progressMeta,
        selectedNodeIds,
        sendMessageStream,  // Используем streaming версию
        clearSession,
        setSocket,
    } = useAIAssistantStore()

    const { sourceNodes, contentNodes, widgetNodes, commentNodes } = useBoardStore()
    const setFilters = useFilterStore((state) => state.setFilters)
    const setFilterPanelOpen = useFilterStore((state) => state.setFilterPanelOpen)
    const [inputValue, setInputValue] = useState('')
    const messagesContainerRef = useRef<HTMLDivElement>(null)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const shouldAutoScrollRef = useRef(true)

    // Setup AI streaming handlers
    useAIStreaming(contextId, scope)

    // На доске сокет задаётся в BoardCanvas. На дашборде отдельного board-сокета нет — подключаем Socket.IO с JWT для стрима прогресса.
    const token = useAuthStore((s) => s.token)
    useEffect(() => {
        if (scope !== 'dashboard') return
        if (!token) return
        const socket = socketService.connect(token)
        setSocket(socket)
        return () => {
            setSocket(null)
            socketService.disconnect()
        }
    }, [scope, token, setSocket])

    const updateAutoScrollState = () => {
        const container = messagesContainerRef.current
        if (!container) return
        const distanceFromBottom =
            container.scrollHeight - container.scrollTop - container.clientHeight
        // Если пользователь ушел выше, не перехватываем скролл.
        shouldAutoScrollRef.current = distanceFromBottom < 120
    }

    // Auto-scroll to bottom on new messages/progress updates.
    // During active streaming we force-follow the last message.
    useEffect(() => {
        const container = messagesContainerRef.current
        if (!container) return
        if (!isStreaming && !shouldAutoScrollRef.current) return
        container.scrollTop = container.scrollHeight
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages.length, currentStreamMessage, isLoading, isStreaming, progressSteps.length, progressMeta.current])

    const handleSend = async () => {
        if (!inputValue.trim() || isLoading || isStreaming) return

        const message = inputValue.trim()
        setInputValue('')
        // Пользователь явно отправил сообщение — возвращаем автоскролл к низу.
        shouldAutoScrollRef.current = true
        await sendMessageStream(contextId, message, {
            // Auto-filter is always enabled; UI toggle removed by design.
            allowAutoFilter: true,
        }, scope)
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    const handleClearSession = async () => {
        await clearSession(contextId, scope)
    }

    // Context indicator
    const totalNodes = sourceNodes.length + contentNodes.length + widgetNodes.length + commentNodes.length
    const contextText = selectedNodeIds.length > 0
        ? `Выбрано ${selectedNodeIds.length} нод`
        : `${totalNodes} нод на доске`
    const hasScrollableMessages = messages.length > 0 || isStreaming || isLoading
    const emptyStateTargetText = scope === 'dashboard' ? 'дашборде' : 'доске'

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            {showHeader && (
                <div className="flex items-center justify-between px-4 py-2 border-b border-border">
                    <div className="flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-primary" />
                        <h2 className="font-semibold text-sm">ИИ-ассистент</h2>
                    </div>
                    <div className="flex items-center gap-1">
                        {messages.length > 0 && (
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={handleClearSession}
                                title="Очистить историю"
                                className="h-7 w-7"
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                        )}
                    </div>
                </div>
            )}

            {/* Context indicator only for board scope (hidden for dashboard/view mode) */}
            {scope === 'board' && (
                <div className="px-4 py-1.5 bg-muted/50 text-xs text-muted-foreground border-b border-border">
                    <span>📊 Контекст: {contextText}</span>
                </div>
            )}

            {/* Messages */}
            <div
                ref={messagesContainerRef}
                onScroll={updateAutoScrollState}
                className={cn(
                    'flex-1 p-2',
                    hasScrollableMessages ? 'overflow-y-auto space-y-2' : 'overflow-y-hidden'
                )}
            >
                {messages.length === 0 && !isStreaming ? (
                    <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                        <Sparkles className="w-12 h-12 mb-4 text-primary/30" />
                        <p className="text-sm">
                            Привет! Я ИИ-ассистент GigaBoard.
                            <br />
                            {`Задайте мне вопрос о вашем ${emptyStateTargetText}.`}
                        </p>
                    </div>
                ) : (
                    messages.map((msg, idx) => (
                        <MessageBubble
                            key={msg.id || idx}
                            message={msg}
                            onApplyFilter={(expr) => {
                                setFilters(expr)
                                setFilterPanelOpen(true)
                            }}
                        />
                    ))
                )}

                {/* Streaming progress / message */}
                {isStreaming && !currentStreamMessage && progressSteps.length > 0 && (
                    <div className="flex justify-start">
                        <div className="max-w-[95%]">
                            <MultiAgentProgressBlock
                                runningText="Мультиагент выполняется..."
                                progressMeta={progressMeta}
                                progressSteps={progressSteps}
                                variant="primary"
                            />
                        </div>
                    </div>
                )}
                {isStreaming && currentStreamMessage && (
                    <div className="flex justify-start">
                        <div className="max-w-[95%] bg-muted rounded-lg px-3 py-1.5">
                            <div className="text-sm whitespace-pre-wrap">
                                {currentStreamMessage}
                                <span className="inline-block w-1.5 h-3.5 ml-1 bg-primary animate-pulse" />
                            </div>
                        </div>
                    </div>
                )}

                {isLoading && !isStreaming && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        AI думает...
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-2 border-t border-border">
                <div className="flex gap-2">
                    <Textarea
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Спросите что-нибудь..."
                        className="min-h-[48px] max-h-[120px] resize-none"
                        disabled={isLoading || isStreaming}
                    />
                    <Button
                        onClick={handleSend}
                        disabled={!inputValue.trim() || isLoading || isStreaming}
                        size="icon"
                        className="h-[48px] w-[48px] shrink-0"
                    >
                        {isStreaming ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                            <Send className="w-5 h-5" />
                        )}
                    </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                    Нажмите Enter для отправки, Shift+Enter для новой строки
                </p>
            </div>
        </div>
    )
}

interface MessageBubbleProps {
    message: {
        role: MessageRole
        content: string
        context?: AIContextUsed
        suggested_actions?: any[]
    }
    onApplyFilter?: (filterExpression: FilterExpression) => void
}

function MessageBubble({ message, onApplyFilter }: MessageBubbleProps) {
    const isUser = message.role === 'user'

    return (
        <div className={cn(
            'flex',
            isUser ? 'justify-end' : 'justify-start'
        )}>
            <div className={cn(
                'max-w-[95%] rounded-lg px-3 py-1.5 text-sm',
                isUser
                    ? 'bg-primary/15 text-foreground'
                    : 'bg-muted text-foreground'
            )}>
                {isUser ? (
                    <p className="whitespace-pre-wrap break-words">{message.content}</p>
                ) : (
                    <div className="prose prose-sm dark:prose-invert max-w-none break-words [&_pre]:text-xs [&_pre]:py-1.5 [&_pre]:px-2 [&_ul]:my-1 [&_ol]:my-1 [&_p]:my-0.5">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.content}
                        </ReactMarkdown>
                    </div>
                )}

                {/* Suggested Actions */}
                {message.suggested_actions && message.suggested_actions.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border/20 space-y-1">
                        <p className="text-xs opacity-70 mb-1">Рекомендуемые действия:</p>
                        {message.suggested_actions.map((action, idx) => (
                            action?.action === 'apply_filter' ? (
                                <button
                                    key={idx}
                                    type="button"
                                    className="text-xs px-2 py-1 rounded bg-background/20 hover:bg-background/40 text-left w-full"
                                    onClick={() => {
                                        const expression = action?.params?.filter_expression
                                        if (expression && onApplyFilter) {
                                            onApplyFilter(expression as FilterExpression)
                                        }
                                    }}
                                >
                                    {action.description || 'Применить предложенный фильтр'}
                                </button>
                            ) : (
                                <div
                                    key={idx}
                                    className="text-xs px-2 py-1 rounded bg-background/20"
                                >
                                    {action.label || action.description || JSON.stringify(action)}
                                </div>
                            )
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
