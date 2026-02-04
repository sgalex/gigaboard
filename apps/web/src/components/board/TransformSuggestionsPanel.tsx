import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, Filter, BarChart2, Lightbulb, Shuffle, Calculator, AlertCircle, FileText, List, Table2, Search, Wand2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { contentNodesAPI } from '@/services/api'

interface TransformSuggestion {
    id: string
    label: string
    prompt: string
    category: 'filter' | 'aggregate' | 'merge' | 'reshape' | 'compute' | 'extract' | 'summarize' | 'structure' | 'analyze' | 'transform'
    confidence: number
    description?: string
    reasoning?: string
}

interface TransformSuggestionsPanelProps {
    contentNodeId: string
    chatHistory: Array<{ role: string; content: string }>
    currentCode?: string
    onSuggestionClick: (prompt: string) => void
}

const CATEGORY_ICONS: Record<TransformSuggestion['category'], React.ComponentType<{ className?: string }>> = {
    // Табличные операции
    filter: Filter,
    aggregate: BarChart2,
    merge: Shuffle,
    reshape: Shuffle,
    compute: Calculator,
    // Текстовые операции
    extract: Search,
    summarize: FileText,
    structure: Table2,
    analyze: Lightbulb,
    transform: Wand2,
}

const CATEGORY_LABELS: Record<TransformSuggestion['category'], string> = {
    // Табличные операции
    filter: 'Фильтрация',
    aggregate: 'Агрегация',
    merge: 'Объединение',
    reshape: 'Перестройка',
    compute: 'Вычисления',
    // Текстовые операции
    extract: 'Извлечение',
    summarize: 'Суммаризация',
    structure: 'Структурирование',
    analyze: 'Анализ',
    transform: 'Преобразование',
}

const CATEGORY_COLORS: Record<TransformSuggestion['category'], string> = {
    // Табличные операции
    filter: 'bg-blue-500 text-white hover:bg-blue-600',
    aggregate: 'bg-green-500 text-white hover:bg-green-600',
    merge: 'bg-purple-500 text-white hover:bg-purple-600',
    reshape: 'bg-orange-500 text-white hover:bg-orange-600',
    compute: 'bg-pink-500 text-white hover:bg-pink-600',
    // Текстовые операции
    extract: 'bg-cyan-500 text-white hover:bg-cyan-600',
    summarize: 'bg-teal-500 text-white hover:bg-teal-600',
    structure: 'bg-indigo-500 text-white hover:bg-indigo-600',
    analyze: 'bg-amber-500 text-white hover:bg-amber-600',
    transform: 'bg-violet-500 text-white hover:bg-violet-600',
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
            <div className="flex flex-wrap gap-1.5">
                {suggestions.map((suggestion) => {
                    const Icon = CATEGORY_ICONS[suggestion.category] || Lightbulb

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
                                    'cursor-pointer text-[10px] px-2 py-0.5 flex items-center gap-1 transition-all max-w-[140px]',
                                    CATEGORY_COLORS[suggestion.category]
                                )}
                                onClick={() => onSuggestionClick(suggestion.prompt)}
                            >
                                <Icon className="w-2.5 h-2.5 flex-shrink-0" />
                                <span className="truncate">{suggestion.label}</span>
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
                        const Icon = CATEGORY_ICONS[suggestion.category] || Lightbulb

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
                                                variant="secondary"
                                                className={cn(
                                                    'text-xs px-1.5 py-0',
                                                    CATEGORY_COLORS[suggestion.category]
                                                )}
                                            >
                                                {CATEGORY_LABELS[suggestion.category]}
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-gray-500 mb-1">
                                            Уверенность: {Math.round(suggestion.confidence * 100)}%
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
