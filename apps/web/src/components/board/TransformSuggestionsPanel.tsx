import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, Filter, BarChart2, Calculator, ArrowUpDown, Eraser, Shuffle, Grid3x3, AlertCircle, Lightbulb } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { contentNodesAPI } from '@/services/api'

interface TransformSuggestion {
    id: string
    label: string
    prompt: string
    type: 'filter' | 'aggregation' | 'calculation' | 'sorting' | 'cleaning' | 'merge' | 'reshape'
    relevance: number  // 0.0-1.0
    category: string  // Legacy field
    confidence: number  // Legacy field
    description?: string
    reasoning?: string
}

interface TransformSuggestionsPanelProps {
    contentNodeId: string
    chatHistory: Array<{ role: string; content: string }>
    currentCode?: string
    onSuggestionClick: (prompt: string) => void
}

const TYPE_ICONS: Record<TransformSuggestion['type'], React.ComponentType<{ className?: string }>> = {
    filter: Filter,
    aggregation: BarChart2,
    calculation: Calculator,
    sorting: ArrowUpDown,
    cleaning: Eraser,
    merge: Shuffle,
    reshape: Grid3x3,
}

const TYPE_LABELS: Record<TransformSuggestion['type'], string> = {
    filter: 'Фильтрация',
    aggregation: 'Агрегация',
    calculation: 'Вычисления',
    sorting: 'Сортировка',
    cleaning: 'Очистка',
    merge: 'Объединение',
    reshape: 'Перестройка',
}

const TYPE_COLORS: Record<TransformSuggestion['type'], string> = {
    filter: 'bg-blue-500 text-white hover:bg-blue-600',
    aggregation: 'bg-green-500 text-white hover:bg-green-600',
    calculation: 'bg-purple-500 text-white hover:bg-purple-600',
    sorting: 'bg-orange-500 text-white hover:bg-orange-600',
    cleaning: 'bg-pink-500 text-white hover:bg-pink-600',
    merge: 'bg-cyan-500 text-white hover:bg-cyan-600',
    reshape: 'bg-amber-500 text-white hover:bg-amber-600',
}

// Relevance-based badge colors (border/text, not background)
const getRelevanceBadgeColor = (relevance: number): string => {
    if (relevance >= 0.9) return 'border-red-500 text-red-700 bg-red-50'  // Critical
    if (relevance >= 0.7) return 'border-orange-500 text-orange-700 bg-orange-50'  // High
    if (relevance >= 0.5) return 'border-yellow-500 text-yellow-700 bg-yellow-50'  // Medium
    if (relevance >= 0.3) return 'border-gray-400 text-gray-600 bg-gray-50'  // Low
    return 'border-gray-300 text-gray-500 bg-gray-50'  // Very low
}

export const TransformSuggestionsPanel = ({
    contentNodeId,
    chatHistory,
    currentCode,
    onSuggestionClick,
}: TransformSuggestionsPanelProps) => {
    const [suggestions, setSuggestions] = useState<TransformSuggestion[]>([])
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
            const response = await contentNodesAPI.analyzeTransformSuggestions(contentNodeId, {
                chat_history: chatHistory,
                current_code: currentCode || null,
            })

            setSuggestions(response.data.suggestions || [])
        } catch (err: any) {
            console.error('Failed to load transform suggestions:', err)
            console.error('Request details:', {
                contentNodeId,
                chatHistoryLength: chatHistory.length,
                hasCode: !!currentCode,
            })

            // Better error messages
            if (err.response?.status === 503) {
                const detail = err.response?.data?.detail || 'Service unavailable'
                if (detail.includes('Redis') || detail.includes('GigaChat')) {
                    setError('AI рекомендации недоступны. Проверьте подключение к Redis и GigaChat.')
                } else {
                    setError('Сервис рекомендаций временно недоступен')
                }
            } else if (err.response?.status === 404) {
                // Endpoint not implemented yet - graceful fallback
                console.warn('Transform suggestions endpoint not implemented yet')
                setSuggestions([])
                return
            } else {
                setError('Не удалось загрузить рекомендации')
            }
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        loadSuggestions()
    }, [contentNodeId])

    // Reload suggestions when code changes (after AI response)
    useEffect(() => {
        if (currentCode) {
            loadSuggestions()
        }
    }, [currentCode])

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-4">
                <Loader2 className="w-4 h-4 animate-spin text-purple-600" />
                <span className="ml-2 text-xs text-gray-600">Анализ данных...</span>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center p-4 text-red-600">
                <AlertCircle className="w-4 h-4 mr-2" />
                <span className="text-xs">{error}</span>
            </div>
        )
    }

    if (suggestions.length === 0) {
        return (
            <div className="p-4 text-center text-gray-500 text-xs">
                <Lightbulb className="w-6 h-6 mx-auto mb-1 opacity-50" />
                <p>Начните диалог, чтобы увидеть рекомендации</p>
            </div>
        )
    }

    return (
        <div className="p-2 border-t">
            <div className="text-xs font-medium mb-1.5 text-muted-foreground">✨ Рекомендации трансформаций</div>

            {/* Compact tag view with tooltips */}
            <div className="grid w-full grid-cols-6 gap-1.5">
                {suggestions.map((suggestion, index) => {
                    const Icon = TYPE_ICONS[suggestion.type] || Lightbulb
                    const n = suggestions.length
                    const r = n % 3
                    const colSpan =
                        r === 1 && index === n - 1
                            ? 'col-span-6'
                            : r === 2 && index >= n - 2
                              ? 'col-span-3'
                              : 'col-span-2'

                    return (
                        <div
                            key={suggestion.id}
                            className={cn('min-w-0 w-full', colSpan)}
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
                                    'w-full min-w-0 cursor-pointer text-[11px] px-3 py-0.5 flex items-center gap-1.5 transition-all justify-start',
                                    TYPE_COLORS[suggestion.type]
                                )}
                                onClick={() => onSuggestionClick(suggestion.prompt)}
                            >
                                <Icon className="w-2.5 h-2.5 flex-shrink-0" />
                                <span className="truncate min-w-0 flex-1">
                                    {suggestion.label}
                                </span>
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
                        const Icon = TYPE_ICONS[suggestion.type] || Lightbulb

                        return (
                            <>
                                <div className="flex items-start gap-2 mb-2">
                                    <Icon className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-600" />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h4 className="text-sm font-semibold text-gray-900">
                                                {suggestion.label}
                                            </h4>
                                            <Badge
                                                variant="outline"
                                                className={cn(
                                                    'text-xs px-1.5 py-0 border',
                                                    getRelevanceBadgeColor(suggestion.relevance)
                                                )}
                                            >
                                                {Math.round(suggestion.relevance * 100)}%
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-gray-500 mb-1">
                                            {TYPE_LABELS[suggestion.type]}
                                        </p>
                                    </div>
                                </div>

                                {suggestion.description && (
                                    <p className="text-xs text-gray-700 leading-relaxed mb-2">
                                        {suggestion.description}
                                    </p>
                                )}

                                {suggestion.reasoning && (
                                    <div className="pt-2 border-t border-gray-100">
                                        <p className="text-xs text-gray-500 italic">
                                            💡 {suggestion.reasoning}
                                        </p>
                                    </div>
                                )}

                                <div className="pt-2 border-t border-gray-100 mt-2">
                                    <p className="text-xs text-gray-600 font-medium">
                                        📝 Промпт для AI:
                                    </p>
                                    <p className="text-xs text-gray-500 mt-1 italic">
                                        "{suggestion.prompt}"
                                    </p>
                                </div>

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
