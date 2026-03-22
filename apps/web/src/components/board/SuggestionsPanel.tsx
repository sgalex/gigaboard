import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import type { LucideIcon } from 'lucide-react'
import {
    Loader2,
    Sparkles,
    TrendingUp,
    Lightbulb,
    Library,
    Palette,
    AlertCircle,
    BarChart3,
    LineChart,
    PieChart,
    ScatterChart,
    Flame,
    Table2,
    LayoutDashboard,
    Map,
    Filter,
    Gauge,
    LayoutGrid,
    Radar,
    ChartColumn,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { contentNodesAPI } from '@/services/api'

interface Suggestion {
    id: string
    type: 'improvement' | 'alternative' | 'insight' | 'library' | 'style'
    /** Тип визуализации для иконки/цвета бейджа (с бэкенда) */
    viz_category?: string
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

const SUGGESTION_TYPE_ICONS = {
    improvement: Sparkles,
    alternative: TrendingUp,
    insight: Lightbulb,
    library: Library,
    style: Palette,
}

const VIZ_KEYS = new Set([
    'bar',
    'line',
    'pie',
    'scatter',
    'heatmap',
    'table',
    'kpi',
    'map',
    'funnel',
    'gauge',
    'treemap',
    'radar',
    'chart',
])

const VIZ_BADGE: Record<
    string,
    { Icon: LucideIcon; className: string; label: string }
> = {
    bar: {
        Icon: BarChart3,
        className:
            'border-gray-200 bg-blue-50 text-blue-950 border-l-[3px] border-l-blue-600 hover:bg-blue-100',
        label: 'Столбцы',
    },
    line: {
        Icon: LineChart,
        className:
            'border-gray-200 bg-emerald-50 text-emerald-950 border-l-[3px] border-l-emerald-600 hover:bg-emerald-100',
        label: 'Линия',
    },
    pie: {
        Icon: PieChart,
        className:
            'border-gray-200 bg-violet-50 text-violet-950 border-l-[3px] border-l-violet-600 hover:bg-violet-100',
        label: 'Круг / доли',
    },
    scatter: {
        Icon: ScatterChart,
        className:
            'border-gray-200 bg-cyan-50 text-cyan-950 border-l-[3px] border-l-cyan-600 hover:bg-cyan-100',
        label: 'Точки',
    },
    heatmap: {
        Icon: Flame,
        className:
            'border-gray-200 bg-orange-50 text-orange-950 border-l-[3px] border-l-orange-600 hover:bg-orange-100',
        label: 'Тепловая карта',
    },
    table: {
        Icon: Table2,
        className:
            'border-gray-200 bg-slate-50 text-slate-900 border-l-[3px] border-l-slate-600 hover:bg-slate-100',
        label: 'Таблица',
    },
    kpi: {
        Icon: LayoutDashboard,
        className:
            'border-gray-200 bg-amber-50 text-amber-950 border-l-[3px] border-l-amber-600 hover:bg-amber-100',
        label: 'KPI',
    },
    map: {
        Icon: Map,
        className:
            'border-gray-200 bg-teal-50 text-teal-950 border-l-[3px] border-l-teal-600 hover:bg-teal-100',
        label: 'Карта',
    },
    funnel: {
        Icon: Filter,
        className:
            'border-gray-200 bg-pink-50 text-pink-950 border-l-[3px] border-l-pink-600 hover:bg-pink-100',
        label: 'Воронка',
    },
    gauge: {
        Icon: Gauge,
        className:
            'border-gray-200 bg-indigo-50 text-indigo-950 border-l-[3px] border-l-indigo-600 hover:bg-indigo-100',
        label: 'Датчик',
    },
    treemap: {
        Icon: LayoutGrid,
        className:
            'border-gray-200 bg-lime-50 text-lime-950 border-l-[3px] border-l-lime-600 hover:bg-lime-100',
        label: 'Treemap',
    },
    radar: {
        Icon: Radar,
        className:
            'border-gray-200 bg-rose-50 text-rose-950 border-l-[3px] border-l-rose-600 hover:bg-rose-100',
        label: 'Радар',
    },
    chart: {
        Icon: ChartColumn,
        className:
            'border-gray-200 bg-gray-50 text-gray-900 border-l-[3px] border-l-gray-500 hover:bg-gray-100',
        label: 'График',
    },
}

function vizConfig(viz?: string) {
    const key =
        viz && VIZ_KEYS.has(viz.toLowerCase()) ? viz.toLowerCase() : 'chart'
    return VIZ_BADGE[key] ?? VIZ_BADGE.chart
}

const PRIORITY_DOT = {
    high: 'bg-red-500',
    medium: 'bg-amber-400',
    low: 'bg-gray-400',
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
    const isFirstRender = useRef(true)

    const loadSuggestions = async () => {
        if (!contentNodeId) return

        setIsLoading(true)
        setError(null)

        try {
            const response = await contentNodesAPI.analyzeSuggestions(contentNodeId, {
                chat_history: chatHistory,
                current_widget_code: currentWidgetCode || null,
                max_suggestions: 6,
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

    // Reload suggestions when contentNodeId changes or when currentWidgetCode changes
    // Skip first render to wait for currentWidgetCode to be set in edit mode
    useEffect(() => {
        if (isFirstRender.current) {
            isFirstRender.current = false
            // In edit mode (currentWidgetCode exists), wait for it to be set
            // In new widget mode (currentWidgetCode undefined), load immediately
            if (currentWidgetCode === undefined) {
                // New widget - load suggestions immediately
                loadSuggestions()
            }
            return
        }

        loadSuggestions()
    }, [contentNodeId, currentWidgetCode])

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Loader2 className="w-6 h-6 animate-spin text-purple-600" />
                <span className="ml-2 text-sm text-gray-600">Загрузка рекомендаций</span>
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
            <div className="grid w-full grid-cols-6 gap-1.5">
                {suggestions.map((suggestion, index) => {
                    const { Icon, className: vizClass } = vizConfig(
                        suggestion.viz_category
                    )
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
                                variant="outline"
                                className={cn(
                                    'w-full min-w-0 cursor-pointer text-[11px] px-3 py-0.5 flex items-center gap-1.5 transition-all justify-start',
                                    vizClass
                                )}
                                onClick={() => onSuggestionClick(suggestion.prompt)}
                            >
                                <Icon className="w-2.5 h-2.5 flex-shrink-0 opacity-90" />
                                <span className="truncate min-w-0 flex-1">
                                    {suggestion.title}
                                </span>
                                <span
                                    className={cn(
                                        'w-1.5 h-1.5 rounded-full flex-shrink-0',
                                        PRIORITY_DOT[suggestion.priority]
                                    )}
                                    title={
                                        suggestion.priority === 'high'
                                            ? 'Высокий приоритет'
                                            : suggestion.priority === 'medium'
                                              ? 'Средний приоритет'
                                              : 'Низкий приоритет'
                                    }
                                />
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
                        const { Icon: VizIcon, label: vizLabel } = vizConfig(
                            suggestion.viz_category
                        )
                        const TypeIcon =
                            SUGGESTION_TYPE_ICONS[suggestion.type] || Sparkles

                        return (
                            <>
                                <div className="flex items-start gap-2 mb-2">
                                    <VizIcon className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-700" />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1 flex-wrap">
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
                                        <p className="text-xs text-gray-500 mb-0.5">
                                            <span className="font-medium text-gray-600">
                                                {vizLabel}
                                            </span>
                                            <span className="mx-1 text-gray-300">·</span>
                                            <TypeIcon className="w-3 h-3 inline align-text-bottom mr-0.5" />
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
