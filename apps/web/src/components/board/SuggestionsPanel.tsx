import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, Sparkles, TrendingUp, Lightbulb, Library, Palette, AlertCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { contentNodesAPI } from '@/services/api'

interface Suggestion {
    id: string
    type: 'improvement' | 'alternative' | 'insight' | 'library' | 'style'
    priority: 'high' | 'medium' | 'low'
    title: string
    description: string
    prompt: string
    reasoning?: string
}

interface SuggestionsPanelProps {
    contentNodeId: string
    chatHistory: Array<{ role: string; content: string }>
    currentWidgetCode?: string
    onSuggestionClick: (prompt: string) => void
}

const SUGGESTION_ICONS = {
    improvement: Sparkles,
    alternative: TrendingUp,
    insight: Lightbulb,
    library: Library,
    style: Palette,
}

const PRIORITY_COLORS = {
    high: 'border-red-500 bg-red-50',
    medium: 'border-yellow-500 bg-yellow-50',
    low: 'border-gray-300 bg-gray-50',
}

const PRIORITY_BADGE_COLORS = {
    high: 'bg-red-500 text-white hover:bg-red-600',
    medium: 'bg-yellow-500 text-white hover:bg-yellow-600',
    low: 'bg-gray-400 text-white hover:bg-gray-500',
}

const TYPE_LABELS = {
    improvement: 'Улучшение',
    alternative: 'Альтернатива',
    insight: 'Инсайт',
    library: 'Библиотека',
    style: 'Стиль',
}

export const SuggestionsPanel = ({
    contentNodeId,
    chatHistory,
    currentWidgetCode,
    onSuggestionClick,
}: SuggestionsPanelProps) => {
    const [suggestions, setSuggestions] = useState<Suggestion[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [hoveredSuggestion, setHoveredSuggestion] = useState<string | null>(null)
    const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 })
    const badgeRefs = useRef<{ [key: string]: HTMLDivElement | null }>({})

    const loadSuggestions = async () => {
        if (!contentNodeId) return

        setIsLoading(true)
        setError(null)

        try {
            const response = await contentNodesAPI.analyzeSuggestions(contentNodeId, {
                chat_history: chatHistory,
                current_widget_code: currentWidgetCode || null,
                max_suggestions: 8,
            })

            setSuggestions(response.data.suggestions)
        } catch (err: any) {
            console.error('Failed to load suggestions:', err)
            console.error('Request details:', {
                contentNodeId,
                chatHistoryLength: chatHistory.length,
                hasWidgetCode: !!currentWidgetCode,
            })

            // Better error messages based on status code
            if (err.response?.status === 503) {
                const detail = err.response?.data?.detail || 'Service unavailable'
                console.error('Backend error:', err.response.data)

                if (detail.includes('Redis') || detail.includes('GigaChat')) {
                    setError('AI рекомендации недоступны. Проверьте подключение к Redis и GigaChat.')
                } else {
                    setError('Сервис рекомендаций временно недоступен')
                }
            } else if (err.response?.data) {
                console.error('Backend error:', err.response.data)
                setError('Не удалось загрузить рекомендации')
            } else {
                setError('Не удалось загрузить рекомендации')
            }
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        loadSuggestions()
    }, [contentNodeId]) // Reload when contentNodeId changes

    // Reload suggestions only when widget is rebuilt (currentWidgetCode changes)
    useEffect(() => {
        if (currentWidgetCode) {
            loadSuggestions()
        }
    }, [currentWidgetCode])

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Loader2 className="w-6 h-6 animate-spin text-purple-600" />
                <span className="ml-2 text-sm text-gray-600">Анализ данных...</span>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center p-8 text-red-600">
                <AlertCircle className="w-5 h-5 mr-2" />
                <span className="text-sm">{error}</span>
            </div>
        )
    }

    if (suggestions.length === 0) {
        return (
            <div className="p-8 text-center text-gray-500 text-sm">
                <Lightbulb className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>Начните диалог с AI, чтобы увидеть рекомендации</p>
            </div>
        )
    }

    return (
        <div className="p-2">
            {/* Compact tag view with tooltips */}
            <div className="flex flex-wrap gap-1.5">
                {suggestions.map((suggestion) => {
                    const Icon = SUGGESTION_ICONS[suggestion.type]

                    return (
                        <div
                            key={suggestion.id}
                            ref={(el) => (badgeRefs.current[suggestion.id] = el)}
                            onMouseEnter={(e) => {
                                const rect = e.currentTarget.getBoundingClientRect()
                                setTooltipPosition({
                                    top: rect.bottom + window.scrollY + 8,
                                    left: rect.left + window.scrollX
                                })
                                setHoveredSuggestion(suggestion.id)
                            }}
                            onMouseLeave={() => setHoveredSuggestion(null)}
                        >
                            <Badge
                                className={cn(
                                    'cursor-pointer text-[10px] px-2 py-0.5 flex items-center gap-1 transition-all max-w-[120px]',
                                    PRIORITY_BADGE_COLORS[suggestion.priority]
                                )}
                                onClick={() => onSuggestionClick(suggestion.prompt)}
                            >
                                <Icon className="w-2.5 h-2.5 flex-shrink-0" />
                                <span className="truncate">{suggestion.title}</span>
                            </Badge>
                        </div>
                    )
                })}
            </div>

            {/* Global tooltip portal */}
            {hoveredSuggestion && createPortal(
                <div
                    className="fixed w-72 bg-white border border-gray-200 rounded-lg shadow-xl p-3 z-[9999] pointer-events-none"
                    style={{
                        top: `${tooltipPosition.top}px`,
                        left: `${tooltipPosition.left}px`,
                    }}
                >
                    {(() => {
                        const suggestion = suggestions.find(s => s.id === hoveredSuggestion)
                        if (!suggestion) return null
                        const Icon = SUGGESTION_ICONS[suggestion.type]

                        return (
                            <>
                                <div className="flex items-start gap-2 mb-2">
                                    <Icon className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-600" />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h4 className="text-sm font-semibold text-gray-900">
                                                {suggestion.title}
                                            </h4>
                                            <Badge
                                                variant="secondary"
                                                className={cn(
                                                    'text-xs px-1.5 py-0',
                                                    PRIORITY_BADGE_COLORS[suggestion.priority]
                                                )}
                                            >
                                                {suggestion.priority === 'high'
                                                    ? 'Важно'
                                                    : suggestion.priority === 'medium'
                                                        ? 'Средне'
                                                        : 'Низко'}
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-gray-500 mb-1">
                                            {TYPE_LABELS[suggestion.type]}
                                        </p>
                                    </div>
                                </div>

                                <p className="text-xs text-gray-700 leading-relaxed mb-2">
                                    {suggestion.description}
                                </p>

                                {suggestion.reasoning && (
                                    <div className="pt-2 border-t border-gray-100">
                                        <p className="text-xs text-gray-500 italic">
                                            💡 {suggestion.reasoning}
                                        </p>
                                    </div>
                                )}

                                {/* Arrow pointer */}
                                <div className="absolute -top-1 left-4 w-2 h-2 bg-white border-l border-t border-gray-200 transform rotate-45" />
                            </>
                        )
                    })()}
                </div>,
                document.body
            )}
        </div>
    )
}
