/**
 * SourceVitrina - витрина типов источников для drag & drop на canvas.
 * 
 * Отображает все доступные типы источников, которые можно перетащить на доску.
 * См. docs/SOURCE_NODE_CONCEPT_V2.md
 */
import { useState, useEffect } from 'react'
import {
    FileSpreadsheet,
    FileJson,
    FileText,
    Globe,
    Database,
    Search,
    Edit3,
    Radio,
    FileX
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Иконки для каждого типа источника
const SOURCE_ICONS: Record<string, React.ElementType> = {
    csv: FileSpreadsheet,
    json: FileJson,
    excel: FileSpreadsheet,
    document: FileText,
    api: Globe,
    database: Database,
    research: Search,
    manual: Edit3,
    stream: Radio,
}

// Цвета для каждого типа источника
const SOURCE_COLORS: Record<string, string> = {
    csv: 'text-green-500',
    json: 'text-yellow-500',
    excel: 'text-emerald-600',
    document: 'text-blue-500',
    api: 'text-purple-500',
    database: 'text-orange-500',
    research: 'text-pink-500',
    manual: 'text-gray-500',
    stream: 'text-cyan-500',
}

export interface SourceVitrinaItem {
    source_type: string
    display_name: string
    icon: string
    description: string
}

interface SourceVitrinaProps {
    items?: SourceVitrinaItem[]
    onDragStart?: (item: SourceVitrinaItem) => void
    className?: string
}

// Дефолтные items если API недоступно
const DEFAULT_ITEMS: SourceVitrinaItem[] = [
    { source_type: 'csv', display_name: 'CSV', icon: '📊', description: 'CSV файлы' },
    { source_type: 'json', display_name: 'JSON', icon: '📋', description: 'JSON файлы' },
    { source_type: 'excel', display_name: 'Excel', icon: '📗', description: 'Excel файлы' },
    { source_type: 'document', display_name: 'Документ', icon: '📄', description: 'PDF, DOCX, TXT' },
    { source_type: 'api', display_name: 'API', icon: '🔗', description: 'REST API' },
    { source_type: 'database', display_name: 'База данных', icon: '🗄️', description: 'SQL БД' },
    { source_type: 'research', display_name: 'AI Research', icon: '🔍', description: 'Поиск через AI' },
    { source_type: 'manual', display_name: 'Ручной ввод', icon: '✏️', description: 'Создать таблицу' },
    { source_type: 'stream', display_name: 'Стрим', icon: '📡', description: 'Real-time (скоро)' },
]

export function SourceVitrina({ items, onDragStart, className }: SourceVitrinaProps) {
    const [vitrinaItems, setVitrinaItems] = useState<SourceVitrinaItem[]>(items || DEFAULT_ITEMS)
    const [isLoading, setIsLoading] = useState(!items)

    useEffect(() => {
        if (!items) {
            // Fetch from API
            fetchVitrinaItems()
        }
    }, [items])

    const fetchVitrinaItems = async () => {
        try {
            const response = await fetch('/api/v1/source-nodes/vitrina')
            if (response.ok) {
                const data = await response.json()
                setVitrinaItems(data.items || DEFAULT_ITEMS)
            }
        } catch (error) {
            console.warn('Failed to fetch vitrina items, using defaults')
        } finally {
            setIsLoading(false)
        }
    }

    const handleDragStart = (e: React.DragEvent, item: SourceVitrinaItem) => {
        e.dataTransfer.setData('application/json', JSON.stringify({
            type: 'source_node',
            source_type: item.source_type,
            display_name: item.display_name,
        }))
        e.dataTransfer.effectAllowed = 'copy'
        onDragStart?.(item)
    }

    return (
        <div className={cn('grid grid-cols-3 gap-2 p-2', className)}>
            {vitrinaItems.map((item) => {
                const Icon = SOURCE_ICONS[item.source_type] || FileX
                const colorClass = SOURCE_COLORS[item.source_type] || 'text-muted-foreground'
                const isDisabled = item.source_type === 'stream'

                return (
                    <div
                        key={item.source_type}
                        draggable={!isDisabled}
                        onDragStart={(e) => handleDragStart(e, item)}
                        className={cn(
                            'flex flex-col items-center justify-center p-2 rounded-lg',
                            'border border-border bg-card',
                            'transition-all duration-150',
                            isDisabled
                                ? 'opacity-50 cursor-not-allowed'
                                : 'cursor-grab hover:border-primary hover:shadow-sm active:cursor-grabbing',
                        )}
                        title={item.description}
                    >
                        <Icon className={cn('h-6 w-6 mb-1', colorClass)} />
                        <span className="text-xs text-center font-medium truncate w-full">
                            {item.display_name}
                        </span>
                    </div>
                )
            })}
        </div>
    )
}
