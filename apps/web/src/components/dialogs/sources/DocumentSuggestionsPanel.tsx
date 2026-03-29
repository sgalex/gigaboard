/**
 * Панель AI-рекомендаций для чата извлечения из документа (аналог TransformSuggestionsPanel).
 */
import { useState, useEffect, useLayoutEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, Filter, BarChart2, Calculator, ArrowUpDown, Eraser, Shuffle, Grid3x3, AlertCircle, Lightbulb } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { filesAPI } from '@/services/api'
import {
    getInitialTooltipViewportPos,
    placeTooltipInViewport,
    tooltipLayoutEqual,
    type SuggestionTooltipPlacement,
} from '@/lib/suggestionTooltipPlacement'

interface DocumentSuggestionTag {
    id: string
    label: string
    prompt: string
    type: 'filter' | 'aggregation' | 'calculation' | 'sorting' | 'cleaning' | 'merge' | 'reshape'
    relevance: number
    category: string
    confidence: number
    description?: string
    reasoning?: string
}

const SUGGESTIONS_DEBOUNCE_MS = 450

export interface DocumentSuggestionsPayload {
    document_text: string
    document_type: string
    filename: string
    page_count?: number | null
    existing_tables: Array<Record<string, unknown>>
}

interface DocumentSuggestionsPanelProps {
    fileId: string
    documentPayload: DocumentSuggestionsPayload
    chatHistory: Array<{ role: string; content: string }>
    contextFingerprint: string
    suggestionsTabActive: boolean
    isGenerating?: boolean
    suggestionsRefreshKey?: number
    onSuggestionsLoadingChange?: (loading: boolean) => void
    onSuggestionClick: (prompt: string) => void
}

const TYPE_ICONS: Record<DocumentSuggestionTag['type'], React.ComponentType<{ className?: string }>> = {
    filter: Filter,
    aggregation: BarChart2,
    calculation: Calculator,
    sorting: ArrowUpDown,
    cleaning: Eraser,
    merge: Shuffle,
    reshape: Grid3x3,
}

const TYPE_LABELS: Record<DocumentSuggestionTag['type'], string> = {
    filter: 'Фокус / отбор',
    aggregation: 'Сводка / агрегация',
    calculation: 'Производные показатели',
    sorting: 'Упорядочивание',
    cleaning: 'Нормализация',
    merge: 'Сопоставление',
    reshape: 'Структура',
}

function normalizeDocumentSuggestion(raw: Record<string, unknown>): DocumentSuggestionTag {
    const category = String(raw.category ?? '')
    const typeRaw = String(raw.type ?? '')
    const typeMap: Record<string, DocumentSuggestionTag['type']> = {
        filter: 'filter',
        aggregation: 'aggregation',
        aggregate: 'aggregation',
        calculation: 'calculation',
        compute: 'calculation',
        sorting: 'sorting',
        cleaning: 'cleaning',
        merge: 'merge',
        reshape: 'reshape',
    }
    const type =
        (typeMap[typeRaw] || typeMap[category] || 'filter') as DocumentSuggestionTag['type']
    const rel = raw.relevance
    const conf = raw.confidence
    const relevance =
        typeof rel === 'number' ? rel : typeof conf === 'number' ? conf : 0.5
    const confidence = typeof conf === 'number' ? conf : relevance

    return {
        id: String(raw.id ?? ''),
        label: String(raw.label ?? ''),
        prompt: String(raw.prompt ?? ''),
        type,
        relevance,
        category: category || type,
        confidence,
        description: raw.description != null ? String(raw.description) : undefined,
        reasoning: raw.reasoning != null ? String(raw.reasoning) : undefined,
    }
}

const TYPE_COLORS: Record<DocumentSuggestionTag['type'], string> = {
    filter: 'bg-blue-500 text-white hover:bg-blue-600',
    aggregation: 'bg-green-500 text-white hover:bg-green-600',
    calculation: 'bg-purple-500 text-white hover:bg-purple-600',
    sorting: 'bg-orange-500 text-white hover:bg-orange-600',
    cleaning: 'bg-pink-500 text-white hover:bg-pink-600',
    merge: 'bg-cyan-500 text-white hover:bg-cyan-600',
    reshape: 'bg-amber-500 text-white hover:bg-amber-600',
}

const getRelevanceBadgeColor = (relevance: number): string => {
    if (relevance >= 0.9) return 'border-red-500 text-red-700 bg-red-50'
    if (relevance >= 0.7) return 'border-orange-500 text-orange-700 bg-orange-50'
    if (relevance >= 0.5) return 'border-yellow-500 text-yellow-700 bg-yellow-50'
    if (relevance >= 0.3) return 'border-gray-400 text-gray-600 bg-gray-50'
    return 'border-gray-300 text-gray-500 bg-gray-50'
}

export function DocumentSuggestionsPanel({
    fileId,
    documentPayload,
    chatHistory,
    contextFingerprint,
    suggestionsTabActive,
    isGenerating = false,
    suggestionsRefreshKey = 0,
    onSuggestionsLoadingChange,
    onSuggestionClick,
}: DocumentSuggestionsPanelProps) {
    const [suggestions, setSuggestions] = useState<DocumentSuggestionTag[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [loadingMode, setLoadingMode] = useState<'load' | 'refresh'>('load')
    const [error, setError] = useState<string | null>(null)
    const [hoveredSuggestion, setHoveredSuggestion] = useState<string | null>(null)
    const [tooltipLayout, setTooltipLayout] = useState<{
        top: number
        left: number
        placement: SuggestionTooltipPlacement
    } | null>(null)
    const badgeRefs = useRef<{ [key: string]: HTMLDivElement | null }>({})
    const tooltipRef = useRef<HTMLDivElement | null>(null)

    const chatHistoryRef = useRef(chatHistory)
    const documentPayloadRef = useRef(documentPayload)
    chatHistoryRef.current = chatHistory
    documentPayloadRef.current = documentPayload

    const lastFetchedFingerprintRef = useRef<string | null>(null)
    const inFlightFingerprintRef = useRef<string | null>(null)
    const contextFingerprintRef = useRef(contextFingerprint)
    contextFingerprintRef.current = contextFingerprint
    const outstandingFetchesRef = useRef(0)
    const skipExternalRefreshClearRef = useRef(true)
    const hasCompletedFetchRef = useRef(false)

    useEffect(() => {
        hasCompletedFetchRef.current = false
    }, [fileId])

    useEffect(() => {
        if (skipExternalRefreshClearRef.current) {
            skipExternalRefreshClearRef.current = false
            return
        }
        lastFetchedFingerprintRef.current = null
    }, [suggestionsRefreshKey])

    useEffect(() => {
        onSuggestionsLoadingChange?.(isLoading)
    }, [isLoading, onSuggestionsLoadingChange])

    useEffect(() => {
        if (!fileId || !suggestionsTabActive) return
        if (lastFetchedFingerprintRef.current === contextFingerprint) return
        if (inFlightFingerprintRef.current === contextFingerprint) return

        setLoadingMode(hasCompletedFetchRef.current ? 'refresh' : 'load')
        setIsLoading(true)
        setError(null)
        setSuggestions([])

        const fpLocked = contextFingerprint
        let debouncePending = true
        const timer = window.setTimeout(() => {
            debouncePending = false
            if (inFlightFingerprintRef.current === fpLocked) return
            inFlightFingerprintRef.current = fpLocked

            void (async () => {
                outstandingFetchesRef.current += 1
                try {
                    const p = documentPayloadRef.current
                    const response = await filesAPI.analyzeDocumentSuggestions(fileId, {
                        chat_history: chatHistoryRef.current,
                        document_text: p.document_text,
                        document_type: p.document_type,
                        filename: p.filename,
                        page_count: p.page_count ?? undefined,
                        existing_tables: p.existing_tables as Array<Record<string, unknown>>,
                    })

                    if (contextFingerprintRef.current !== fpLocked) {
                        return
                    }

                    const list = response.data.suggestions || []
                    setSuggestions(list.map((s) => normalizeDocumentSuggestion(s as Record<string, unknown>)))
                    lastFetchedFingerprintRef.current = fpLocked
                } catch (err: unknown) {
                    console.error('Failed to load document suggestions:', err)
                    const ax = err as { response?: { status?: number; data?: { detail?: string } } }
                    if (contextFingerprintRef.current !== fpLocked) {
                        return
                    }

                    if (ax.response?.status === 503) {
                        const detail = ax.response?.data?.detail || 'Service unavailable'
                        if (detail.includes('Redis') || detail.includes('GigaChat')) {
                            setError('AI рекомендации недоступны. Проверьте подключение к Redis и GigaChat.')
                        } else {
                            setError('Сервис рекомендаций временно недоступен')
                        }
                    } else if (ax.response?.status === 404) {
                        setSuggestions([])
                        lastFetchedFingerprintRef.current = fpLocked
                    } else {
                        setError('Не удалось загрузить рекомендации')
                    }
                } finally {
                    if (inFlightFingerprintRef.current === fpLocked) {
                        inFlightFingerprintRef.current = null
                    }
                    outstandingFetchesRef.current -= 1
                    if (outstandingFetchesRef.current <= 0) {
                        outstandingFetchesRef.current = 0
                        if (contextFingerprintRef.current === fpLocked) {
                            setIsLoading(false)
                            hasCompletedFetchRef.current = true
                        }
                    }
                }
            })()
        }, SUGGESTIONS_DEBOUNCE_MS)

        return () => {
            window.clearTimeout(timer)
            if (debouncePending) {
                setIsLoading(false)
            }
        }
    }, [fileId, contextFingerprint, suggestionsTabActive, suggestionsRefreshKey])

    useLayoutEffect(() => {
        if (!hoveredSuggestion || !tooltipRef.current) return
        const anchor = badgeRefs.current[hoveredSuggestion]?.getBoundingClientRect()
        if (!anchor) return
        const el = tooltipRef.current
        const next = placeTooltipInViewport(anchor, el.offsetWidth, el.offsetHeight)
        setTooltipLayout((prev) => (prev && tooltipLayoutEqual(prev, next) ? prev : next))
    }, [hoveredSuggestion, suggestions])

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-4">
                <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                <span className="ml-2 text-xs text-muted-foreground">
                    {loadingMode === 'refresh' ? 'Обновление рекомендаций' : 'Загрузка рекомендаций'}
                </span>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center p-4 text-destructive">
                <AlertCircle className="h-4 w-4 mr-2 shrink-0" />
                <span className="text-xs">{error}</span>
            </div>
        )
    }

    if (suggestions.length === 0) {
        return (
            <div className="p-4 text-center text-muted-foreground text-xs">
                <Lightbulb className="w-6 h-6 mx-auto mb-1 opacity-50" />
                <p>Нет рекомендаций для текущего документа и истории</p>
                <p className="mt-1 opacity-80">Уточните задачу во вкладке «Сообщение»</p>
            </div>
        )
    }

    return (
        <div className={cn('p-1', isGenerating && 'opacity-60')} aria-busy={isGenerating || undefined}>
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
                                setTooltipLayout(getInitialTooltipViewportPos(rect))
                                setHoveredSuggestion(suggestion.id)
                            }}
                            onMouseLeave={() => {
                                setHoveredSuggestion(null)
                                setTooltipLayout(null)
                            }}
                        >
                            <Badge
                                className={cn(
                                    'w-full min-w-0 cursor-pointer text-[11px] px-3 py-0.5 flex items-center gap-1.5 transition-all justify-start',
                                    TYPE_COLORS[suggestion.type],
                                    isGenerating && 'cursor-not-allowed'
                                )}
                                onClick={() => {
                                    if (isGenerating) return
                                    onSuggestionClick(suggestion.prompt)
                                }}
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

            {hoveredSuggestion && tooltipLayout && createPortal(
                <div
                    ref={tooltipRef}
                    className="fixed w-72 bg-popover border rounded-lg shadow-xl p-3 z-[9999] pointer-events-none text-popover-foreground"
                    style={{
                        top: `${tooltipLayout.top}px`,
                        left: `${tooltipLayout.left}px`,
                    }}
                >
                    {(() => {
                        const suggestion = suggestions.find(s => s.id === hoveredSuggestion)
                        if (!suggestion) return null
                        const Icon = TYPE_ICONS[suggestion.type] || Lightbulb
                        const placement = tooltipLayout.placement

                        return (
                            <>
                                <div className="flex items-start gap-2 mb-2">
                                    <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h4 className="text-sm font-semibold">
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
                                        <p className="text-xs text-muted-foreground mb-1">
                                            {TYPE_LABELS[suggestion.type]}
                                        </p>
                                    </div>
                                </div>

                                {suggestion.description && (
                                    <p className="text-xs leading-relaxed mb-2">
                                        {suggestion.description}
                                    </p>
                                )}

                                {suggestion.reasoning && (
                                    <div className="pt-2 border-t">
                                        <p className="text-xs text-muted-foreground italic">
                                            {suggestion.reasoning}
                                        </p>
                                    </div>
                                )}

                                <div className="pt-2 border-t mt-2">
                                    <p className="text-xs font-medium">
                                        Промпт для чата:
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-1 italic">
                                        &quot;{suggestion.prompt}&quot;
                                    </p>
                                </div>

                                {placement === 'below' ? (
                                    <div className="absolute -top-1 left-4 z-10 w-2 h-2 bg-popover border-l border-t rotate-45" />
                                ) : (
                                    <div className="absolute -bottom-1 left-4 z-10 w-2 h-2 bg-popover border-r border-b rotate-45" />
                                )}
                            </>
                        )
                    })()}
                </div>,
                document.body
            )}
        </div>
    )
}
