/**
 * AI Assistant Panel - чат-панель для общения с AI помощником
 * См. docs/AI_ASSISTANT.md
 */
import { useState, useRef, useEffect } from 'react'
import { Send, Trash2, Sparkles, Loader2 } from 'lucide-react'
import { useAIAssistantStore } from '@/store/aiAssistantStore'
import { useBoardStore } from '@/store/boardStore'
import { useAIStreaming } from '@/hooks/useAIStreaming'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { MessageRole } from '@/types'

interface AIAssistantPanelProps {
    boardId: string
}

export function AIAssistantPanel({ boardId }: AIAssistantPanelProps) {
    const {
        messages,
        isLoading,
        isStreaming,
        currentStreamMessage,
        selectedNodeIds,
        sendMessageStream,  // Используем streaming версию
        clearSession,
    } = useAIAssistantStore()

    const { sourceNodes, contentNodes, widgetNodes, commentNodes } = useBoardStore()
    const [inputValue, setInputValue] = useState('')
    const messagesEndRef = useRef<HTMLDivElement>(null)

    // Setup AI streaming handlers
    useAIStreaming(boardId)

    // Auto-scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, currentStreamMessage])

    const handleSend = async () => {
        if (!inputValue.trim() || isLoading || isStreaming) return

        const message = inputValue.trim()
        setInputValue('')
        await sendMessageStream(boardId, message)  // Используем streaming
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    const handleClearSession = async () => {
        await clearSession(boardId)
    }

    // Context indicator
    const totalNodes = sourceNodes.length + contentNodes.length + widgetNodes.length + commentNodes.length
    const contextText = selectedNodeIds.length > 0
        ? `Выбрано ${selectedNodeIds.length} нод`
        : `${totalNodes} нод на доске`

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-border">
                <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-primary" />
                    <h2 className="font-semibold text-sm">AI Помощник</h2>
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

            {/* Context Indicator */}
            <div className="px-4 py-1.5 bg-muted/50 text-xs text-muted-foreground border-b border-border">
                📊 Контекст: {contextText}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
                {messages.length === 0 && !isStreaming ? (
                    <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                        <Sparkles className="w-12 h-12 mb-4 text-primary/30" />
                        <p className="text-sm">
                            Привет! Я AI помощник GigaBoard.
                            <br />
                            Задайте мне вопрос о вашей доске.
                        </p>
                    </div>
                ) : (
                    messages.map((msg, idx) => (
                        <MessageBubble key={msg.id || idx} message={msg} />
                    ))
                )}

                {/* Streaming message - показываем по мере получения chunks */}
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
        suggested_actions?: any[]
    }
}

function MessageBubble({ message }: MessageBubbleProps) {
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
                <p className="whitespace-pre-wrap break-words">{message.content}</p>

                {/* Suggested Actions */}
                {message.suggested_actions && message.suggested_actions.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border/20 space-y-1">
                        <p className="text-xs opacity-70 mb-1">Рекомендуемые действия:</p>
                        {message.suggested_actions.map((action, idx) => (
                            <div
                                key={idx}
                                className="text-xs px-2 py-1 rounded bg-background/20"
                            >
                                {action.description || JSON.stringify(action)}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
