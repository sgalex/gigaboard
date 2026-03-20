/**
 * SourceNodeCard - карточка источника данных на доске.
 * 
 * Теперь SourceNode наследует ContentNode и содержит данные.
 * Поэтому карточка показывает как конфигурацию источника, так и извлечённые данные.
 * 
 * См. docs/SOURCE_NODE_CONCEPT.md
 */
import { memo, useState } from 'react'
import { useFilterStore } from '@/store/filterStore'
import { Handle, Position, NodeProps } from '@xyflow/react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from '@/components/ui/dialog'
import {
    FileText,
    Database,
    Globe,
    Radio,
    Edit3,
    MoreVertical,
    RefreshCw,
    Settings,
    FileSpreadsheet,
    FileJson,
    Search,
    Eye,
    Download,
    Edit2,
    Table2,
    CheckCircle,
    AlertCircle,
    Loader2,
    Code,
    TrendingUp,
    Trash2,
    Filter,
} from 'lucide-react'
import { SourceNode, SourceType } from '@/types'
import { useBoardStore } from '@/store/boardStore'
import { cn } from '@/lib/utils'
import { TransformDialog } from './TransformDialog'
import { WidgetDialog } from './WidgetDialog'
import { CSVSourceDialog } from '../dialogs/sources/CSVSourceDialog'
import { JSONSourceDialog } from '../dialogs/sources/JSONSourceDialog'
import { ExcelSourceDialog } from '../dialogs/sources/ExcelSourceDialog'
import { ManualSourceDialog } from '../dialogs/sources/ManualSourceDialog'
import { DatabaseSourceDialog } from '../dialogs/sources/DatabaseSourceDialog'

interface SourceNodeCardProps extends NodeProps {
    data: {
        sourceNode: SourceNode
    }
}

// Icon mapping for source types
const sourceTypeIcons: Record<SourceType, React.ComponentType<{ className?: string }>> = {
    [SourceType.CSV]: FileSpreadsheet,
    [SourceType.JSON]: FileJson,
    [SourceType.EXCEL]: FileSpreadsheet,
    [SourceType.DOCUMENT]: FileText,
    [SourceType.API]: Globe,
    [SourceType.DATABASE]: Database,
    [SourceType.RESEARCH]: Search,
    [SourceType.MANUAL]: Edit3,
    [SourceType.STREAM]: Radio,
}

// Color mapping for source types (gradient-friendly)
const sourceTypeColors: Record<SourceType, { bg: string; gradient: string; light: string }> = {
    [SourceType.CSV]: {
        bg: 'bg-green-500',
        gradient: 'from-green-500 to-emerald-600',
        light: 'bg-green-50 dark:bg-green-950/30'
    },
    [SourceType.JSON]: {
        bg: 'bg-yellow-500',
        gradient: 'from-yellow-500 to-orange-500',
        light: 'bg-yellow-50 dark:bg-yellow-950/30'
    },
    [SourceType.EXCEL]: {
        bg: 'bg-emerald-600',
        gradient: 'from-emerald-500 to-teal-600',
        light: 'bg-emerald-50 dark:bg-emerald-950/30'
    },
    [SourceType.DOCUMENT]: {
        bg: 'bg-blue-500',
        gradient: 'from-blue-500 to-indigo-600',
        light: 'bg-blue-50 dark:bg-blue-950/30'
    },
    [SourceType.API]: {
        bg: 'bg-purple-500',
        gradient: 'from-purple-500 to-pink-600',
        light: 'bg-purple-50 dark:bg-purple-950/30'
    },
    [SourceType.DATABASE]: {
        bg: 'bg-orange-500',
        gradient: 'from-orange-500 to-red-500',
        light: 'bg-orange-50 dark:bg-orange-950/30'
    },
    [SourceType.RESEARCH]: {
        bg: 'bg-pink-500',
        gradient: 'from-pink-500 to-rose-600',
        light: 'bg-pink-50 dark:bg-pink-950/30'
    },
    [SourceType.MANUAL]: {
        bg: 'bg-slate-500',
        gradient: 'from-slate-500 to-gray-600',
        light: 'bg-slate-50 dark:bg-slate-950/30'
    },
    [SourceType.STREAM]: {
        bg: 'bg-cyan-500',
        gradient: 'from-cyan-500 to-blue-500',
        light: 'bg-cyan-50 dark:bg-cyan-950/30'
    },
}

// Human-readable labels for source types
const sourceTypeLabels: Record<SourceType, string> = {
    [SourceType.CSV]: 'CSV',
    [SourceType.JSON]: 'JSON',
    [SourceType.EXCEL]: 'Excel',
    [SourceType.DOCUMENT]: 'Документ',
    [SourceType.API]: 'API',
    [SourceType.DATABASE]: 'База данных',
    [SourceType.RESEARCH]: 'AI Research',
    [SourceType.MANUAL]: 'Ручной ввод',
    [SourceType.STREAM]: 'Стрим',
}

export const SourceNodeCard = memo(({ data, selected }: SourceNodeCardProps) => {
    const { sourceNode } = data
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [isEditingName, setIsEditingName] = useState(false)
    const [tempName, setTempName] = useState('')
    const [showPreviewModal, setShowPreviewModal] = useState(false)
    const [showTransformDialog, setShowTransformDialog] = useState(false)
    const [showWidgetDialog, setShowWidgetDialog] = useState(false)
    const [showSettingsDialog, setShowSettingsDialog] = useState(false)
    const [activeTableIndex, setActiveTableIndex] = useState(0)
    const [editTransformData, setEditTransformData] = useState<{
        messages: Array<{ id: string; role: 'user' | 'assistant'; content: string; timestamp: Date }>
        code: string
        transformationId: string
    } | null>(null)

    const {
        refreshSourceNode,
        updateSourceNode,
        transformContent,
        visualizeContent,
        deleteSourceNode,
        fetchWidgetNodes,
        fetchEdges,
    } = useBoardStore()

    const Icon = sourceTypeIcons[sourceNode.source_type] || FileText
    const colors = sourceTypeColors[sourceNode.source_type] || sourceTypeColors[SourceType.MANUAL]
    const typeLabel = sourceTypeLabels[sourceNode.source_type] || sourceNode.source_type

    // Get content data (SourceNode now has content field from ContentNode inheritance)
    const content = sourceNode.content
    const filteredEntry = useFilterStore((s) => s.filteredNodeData?.[sourceNode.id] ?? null)
    const isFiltered = filteredEntry !== null
    const tables = filteredEntry?.tables ?? content?.tables ?? []
    /** Иконка фильтра: при активном фильтре данные ноды отфильтрованы, значит все таблицы в бейджах затронуты. */
    const tableCount = tables.length
    const totalRows = tables.reduce((sum: number, t: any) => sum + (t.row_count || 0), 0)
    const hasText = !!content?.text
    const hasData = tableCount > 0 || hasText

    // Lineage info
    const lineage = sourceNode.lineage
    const transformCount = lineage?.transformation_history?.length || 0

    // Status calculation
    const getStatus = () => {
        if (isRefreshing) return { icon: Loader2, label: 'Обновление...', color: 'text-blue-500', animate: true }
        if (hasData) return { icon: CheckCircle, label: 'Готов', color: 'text-green-500', animate: false }
        return { icon: AlertCircle, label: 'Нет данных', color: 'text-yellow-500', animate: false }
    }
    const status = getStatus()

    // Handle name edit
    const handleStartEditName = () => {
        setTempName(getTitle())
        setIsEditingName(true)
    }

    const handleSaveName = async () => {
        if (tempName.trim() && tempName !== getTitle()) {
            await updateSourceNode(sourceNode.id, {
                metadata: {
                    ...(sourceNode.metadata || {}),
                    name: tempName.trim()
                }
            })
        }
        setIsEditingName(false)
    }

    const handleCancelEditName = () => {
        setIsEditingName(false)
        setTempName('')
    }

    const handleRefresh = async () => {
        setIsRefreshing(true)
        try {
            await refreshSourceNode(sourceNode.id)
        } finally {
            setIsRefreshing(false)
        }
    }

    // Handle edit transformation (open dialog with saved params)
    const handleEditTransform = () => {
        const transformHistory = lineage?.transformation_history || []
        const lastTransform = transformHistory[transformHistory.length - 1]

        if (!lastTransform) {
            console.warn('No transformation history found')
            setShowTransformDialog(true)
            return
        }

        // Reconstruct chat history from lineage
        // Prefer saved chat_history if available, otherwise create from description
        let chatHistory: Array<{ id: string; role: 'user' | 'assistant'; content: string; timestamp: Date }> = []

        if (lastTransform.chat_history && Array.isArray(lastTransform.chat_history) && lastTransform.chat_history.length > 0) {
            // Use real saved chat history
            console.log('✅ Restoring saved chat history:', lastTransform.chat_history.length, 'messages')
            chatHistory = lastTransform.chat_history.map((msg: any) => ({
                id: crypto.randomUUID(),
                role: msg.role as 'user' | 'assistant',
                content: msg.content,
                timestamp: new Date()
            }))
        } else {
            // Fallback: create from description/prompt
            console.warn('⚠️ No saved chat history, creating from description')
            const userPrompt = lastTransform.prompt || lastTransform.description || 'Transform data'
            chatHistory = [
                {
                    id: crypto.randomUUID(),
                    role: 'user' as const,
                    content: userPrompt,
                    timestamp: new Date()
                },
                {
                    id: crypto.randomUUID(),
                    role: 'assistant' as const,
                    content: `Code created and executed successfully`,
                    timestamp: new Date()
                }
            ]
        }

        setEditTransformData({
            messages: chatHistory,
            code: lastTransform.code_snippet || '',
            transformationId: (lastTransform as any).transformation_id || ''
        })
        setShowTransformDialog(true)
    }

    // Handle delete
    const handleDelete = async () => {
        if (confirm('Удалить источник данных?')) {
            await deleteSourceNode(sourceNode.id)
        }
    }

    // Handle transformation
    const handleTransform = async (code: string, transformationId: string, description?: string, chatHistory?: Array<{ role: string; content: string }>) => {
        await transformContent(sourceNode.id, description || '', code, transformationId, undefined, chatHistory)
    }

    // Handle visualization
    const handleVisualize = async (params: {
        user_prompt?: string
        widget_name?: string
        auto_refresh?: boolean
    }) => {
        await visualizeContent(sourceNode.id, params)
    }

    // Get node title
    const getTitle = (): string => {
        // Strategic logging for SourceNode naming pipeline debugging
        console.log(`[SourceNodeCard] getTitle() for node ${sourceNode.id}:`, {
            'metadata': sourceNode.metadata,
            'metadata?.name': sourceNode.metadata?.name,
            'node_metadata': (sourceNode as any).node_metadata,
            'config?.filename': sourceNode.config?.filename,
            'full sourceNode keys': Object.keys(sourceNode),
        })
        if (sourceNode.metadata?.name) return sourceNode.metadata.name
        if (sourceNode.config?.filename) return sourceNode.config.filename
        return `${typeLabel} источник`
    }

    // Get config summary based on source type
    const getConfigSummary = (): string => {
        const config = sourceNode.config || {}

        switch (sourceNode.source_type) {
            case SourceType.CSV:
            case SourceType.JSON:
            case SourceType.EXCEL:
            case SourceType.DOCUMENT:
                return config.filename || 'Файл не указан'
            case SourceType.DATABASE:
                return `${config.db_type || 'DB'}: ${config.database || 'unknown'}`
            case SourceType.API:
                return config.url || 'URL не указан'
            case SourceType.RESEARCH:
                return config.query?.substring(0, 40) + '...' || 'Запрос не указан'
            case SourceType.STREAM:
                return config.stream_url || 'URL не указан'
            case SourceType.MANUAL:
                return 'Ручной ввод данных'
            default:
                return 'Источник данных'
        }
    }

    // Get data summary
    const getDataSummary = (): string | null => {
        if (!hasData) return null
        if (tableCount === 1) {
            const table = tables[0]
            return `${table.row_count || 0} строк × ${table.columns?.length || 0} столбцов`
        }
        if (tableCount > 1) {
            return `${tableCount} таблиц • ${totalRows} строк`
        }
        return null
    }

    // Handle settings dialog
    const handleOpenSettings = () => {
        setShowSettingsDialog(true)
    }

    // Handle export to Excel
    const handleExportToExcel = async () => {
        try {
            const XLSX = await import('xlsx')
            const workbook = XLSX.utils.book_new()

            if (tables.length === 0) {
                alert('Нет данных для экспорта')
                return
            }

            // Export each table as a separate sheet
            tables.forEach((table, idx) => {
                const rawColumns = table.columns || []
                const columns = rawColumns.map((col: any) => col.name)

                const rawRows = table.rows || []
                const rows = rawRows.map((row: any) => {
                    return columns.map((colName: string) => row?.[colName] ?? '')
                })

                // Prepare data with headers
                const sheetData = [columns, ...rows]
                const worksheet = XLSX.utils.aoa_to_sheet(sheetData)

                // Set column widths
                const colWidths = columns.map(() => ({ wch: 15 }))
                worksheet['!cols'] = colWidths

                // Add sheet with table name (Excel sheet name max 31 chars)
                const sheetName = table.name.substring(0, 31) || `Table_${idx + 1}`
                XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)
            })

            // Generate filename
            const filename = `${getTitle()}_${new Date().toISOString().split('T')[0]}.xlsx`
            XLSX.writeFile(workbook, filename)
        } catch (error) {
            console.error('Export error:', error)
            alert('Ошибка при экспорте в Excel')
        }
    }

    // Render table preview
    const renderTablePreview = (tableIndex: number) => {
        const table = tables[tableIndex]
        if (!table) return null

        // Handle column format
        const rawColumns = table.columns || []
        const columns = rawColumns.map((col) => col.name)

        // Handle row formats: dict rows
        const rawRows = table.rows?.slice(0, 100) || []
        const previewRows = rawRows.map((row) => {
            return columns.map((colName: string) => (row as any)?.[colName] ?? '')
        })

        return (
            <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{table.row_count ?? table.rows?.length ?? 0} строк × {columns.length} столбцов</span>
                </div>
                <div className="overflow-auto max-h-64 border rounded-md">
                    <table className="w-full text-xs">
                        <thead className="bg-muted sticky top-0">
                            <tr>
                                {columns.map((colName: string, idx: number) => (
                                    <th
                                        key={idx}
                                        className="px-2 py-1.5 text-left font-medium border-b border-r last:border-r-0"
                                    >
                                        <div className="truncate max-w-[120px]" title={colName}>
                                            {colName}
                                        </div>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {previewRows.map((row: any[], rowIdx: number) => (
                                <tr key={rowIdx} className="border-b last:border-b-0 hover:bg-muted/50">
                                    {row.map((cellValue: any, colIdx: number) => (
                                        <td
                                            key={colIdx}
                                            className="px-2 py-1 border-r last:border-r-0"
                                        >
                                            <div className="truncate max-w-[120px]" title={String(cellValue ?? '')}>
                                                {cellValue ?? '-'}
                                            </div>
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {(table.row_count || 0) > 5 && (
                    <div className="text-xs text-muted-foreground text-center">
                        Показано 5 из {table.row_count} строк
                    </div>
                )}
            </div>
        )
    }

    return (
        <>
            <Card
                className={cn(
                    'w-[320px] transition-all duration-200 overflow-hidden',
                    'hover:shadow-lg',
                    selected && 'ring-2 ring-primary ring-offset-2 shadow-xl'
                )}
            >
                {/* Colored top accent bar */}
                <div className={cn('h-1.5 bg-gradient-to-r', colors.gradient)} />

                <CardHeader className="p-3 pb-2">
                    <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                            {/* Icon with gradient background */}
                            <div className={cn(
                                'p-2.5 rounded-lg text-white shadow-sm',
                                'bg-gradient-to-br',
                                colors.gradient
                            )}>
                                <Icon className="w-4 h-4" />
                            </div>

                            <div className="flex-1 min-w-0">
                                {isEditingName ? (
                                    <Input
                                        value={tempName}
                                        onChange={(e) => setTempName(e.target.value)}
                                        onBlur={handleSaveName}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') handleSaveName()
                                            if (e.key === 'Escape') handleCancelEditName()
                                        }}
                                        className="h-7 text-sm font-semibold"
                                        autoFocus
                                    />
                                ) : (
                                    <div
                                        className="font-semibold text-sm truncate cursor-pointer hover:text-primary transition-colors"
                                        title={getTitle()}
                                        onDoubleClick={handleStartEditName}
                                    >
                                        {getTitle()}
                                    </div>
                                )}
                                <div className="flex items-center gap-2 mt-0.5">
                                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4">
                                        {typeLabel}
                                    </Badge>
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-0.5">
                            {hasData && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={() => setShowPreviewModal(true)}
                                    title="Просмотр данных"
                                >
                                    <Eye className="h-3.5 w-3.5" />
                                </Button>
                            )}

                            {/* Edit Transformation button (only if has transformation history) */}
                            {transformCount > 0 && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={handleEditTransform}
                                    title="Редактировать трансформацию"
                                >
                                    <Settings className="h-3.5 w-3.5" />
                                </Button>
                            )}

                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={handleOpenSettings}
                                title="Настройки источника"
                            >
                                <Settings className="h-3.5 w-3.5" />
                            </Button>

                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={handleRefresh}
                                disabled={isRefreshing}
                                title="Обновить данные"
                            >
                                <RefreshCw className={cn(
                                    "h-3.5 w-3.5",
                                    isRefreshing && "animate-spin"
                                )} />
                            </Button>

                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="ghost" size="icon" className="h-7 w-7">
                                        <MoreVertical className="h-3.5 w-3.5" />
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-48">
                                    <DropdownMenuItem onClick={handleStartEditName}>
                                        <Edit2 className="mr-2 h-4 w-4" />
                                        Переименовать
                                    </DropdownMenuItem>
                                    {hasData && (
                                        <>
                                            <DropdownMenuSeparator />
                                            <DropdownMenuItem onClick={() => setShowPreviewModal(true)}>
                                                <Eye className="mr-2 h-4 w-4" />
                                                Просмотр данных
                                            </DropdownMenuItem>
                                            <DropdownMenuItem onClick={() => {
                                                console.log('Transform button clicked, hasData:', hasData)
                                                setShowTransformDialog(true)
                                                console.log('showTransformDialog set to true')
                                            }}>
                                                <Code className="mr-2 h-4 w-4" />
                                                Обработка
                                            </DropdownMenuItem>
                                            <DropdownMenuItem onClick={() => setShowWidgetDialog(true)}>
                                                <TrendingUp className="mr-2 h-4 w-4" />
                                                Визуализация
                                            </DropdownMenuItem>
                                        </>
                                    )}
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={handleRefresh} disabled={isRefreshing}>
                                        <RefreshCw className="mr-2 h-4 w-4" />
                                        Обновить данные
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={handleExportToExcel}>
                                        <Download className="mr-2 h-4 w-4" />
                                        Экспорт в Excel
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={handleDelete} className="text-destructive">
                                        <Trash2 className="mr-2 h-4 w-4" />
                                        Удалить
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="p-3 pt-0 space-y-2">
                    {/* Config summary */}
                    <div className="text-xs text-muted-foreground truncate">
                        {getConfigSummary()}
                    </div>

                    {/* Text section (if any) */}
                    {hasText && (
                        <div className="text-xs text-muted-foreground p-2 bg-muted rounded leading-relaxed line-clamp-3">
                            {content?.text}
                        </div>
                    )}

                    {/* Data preview (tables as clickable badges; filter icon inside badge when filter affects this table) */}
                    {tableCount > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                            {tables.map((table, idx: number) => (
                                <Badge
                                    key={idx}
                                    variant="outline"
                                    className="group cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors text-xs gap-1"
                                    onClick={() => {
                                        setActiveTableIndex(idx)
                                        setShowPreviewModal(true)
                                    }}
                                >
                                    <Table2 className="h-3 w-3 shrink-0" />
                                    <span className="font-medium">{table.name}</span>
                                    <span className="ml-0.5 px-1.5 py-0.5 bg-primary/10 rounded text-[10px] font-semibold">
                                        {table.row_count || 0}
                                    </span>
                                    {isFiltered && (
                                        <Filter
                                            className="h-3 w-3 shrink-0 text-blue-600 group-hover:text-primary-foreground ml-0.5 transition-colors"
                                            aria-label="Фильтр затрагивает таблицу"
                                        />
                                    )}
                                </Badge>
                            ))}
                        </div>
                    )}

                    {/* Status bar */}
                    <div className="flex items-center justify-between pt-1 border-t">
                        <div className="flex items-center gap-1.5 text-xs">
                            <status.icon className={cn(
                                "h-3.5 w-3.5",
                                status.color,
                                status.animate && "animate-spin"
                            )} />
                            <span className="text-muted-foreground">{status.label}</span>
                        </div>

                        {getDataSummary() && (
                            <div className="text-xs text-muted-foreground">
                                {getDataSummary()}
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Right handle for transformations */}
            <Handle type="source" position={Position.Right} className="w-3 h-3" id="transform" isConnectable={false} />

            {/* Bottom handle for visualizations */}
            <Handle
                type="source"
                position={Position.Bottom}
                className="w-3 h-3"
                id="visualize"
                isConnectable={false}
            />

            {/* Preview Modal */}
            <Dialog open={showPreviewModal} onOpenChange={setShowPreviewModal}>
                <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <div className={cn('p-1.5 rounded text-white', colors.bg)}>
                                <Icon className="w-4 h-4" />
                            </div>
                            {getTitle()}
                        </DialogTitle>
                        <DialogDescription>
                            {typeLabel} • {getDataSummary() || 'Нет данных'}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex-1 overflow-auto space-y-4">
                        {/* Tables with tabs */}
                        {tableCount > 0 && (
                            <div className="space-y-3">
                                {tableCount > 1 && (
                                    <div className="flex gap-1 border-b">
                                        {tables.map((table: any, idx: number) => (
                                            <button
                                                key={idx}
                                                onClick={() => setActiveTableIndex(idx)}
                                                className={cn(
                                                    'px-3 py-2 text-sm font-medium transition-colors',
                                                    'border-b-2 -mb-px',
                                                    activeTableIndex === idx
                                                        ? 'border-primary text-primary'
                                                        : 'border-transparent text-muted-foreground hover:text-foreground'
                                                )}
                                            >
                                                {table.name}
                                            </button>
                                        ))}
                                    </div>
                                )}

                                {renderTablePreview(activeTableIndex)}
                            </div>
                        )}

                        {!hasData && (
                            <div className="flex items-center justify-center h-32 text-muted-foreground">
                                Нет данных для отображения
                            </div>
                        )}
                    </div>
                </DialogContent>
            </Dialog>

            {/* Transform Dialog */}
            <TransformDialog
                open={showTransformDialog}
                onOpenChange={(open) => {
                    setShowTransformDialog(open)
                    if (!open) setEditTransformData(null) // Clear edit data on close
                }}
                sourceNode={sourceNode as any}
                onTransform={handleTransform}
                initialMessages={editTransformData?.messages}
                initialCode={editTransformData?.code}
                initialTransformationId={editTransformData?.transformationId}
            />

            {/* Widget Dialog */}
            <WidgetDialog
                open={showWidgetDialog}
                onOpenChange={setShowWidgetDialog}
                contentNode={sourceNode as any}
                onVisualize={handleVisualize}
                onWidgetCreated={async () => {
                    await fetchWidgetNodes(sourceNode.board_id)
                    await fetchEdges(sourceNode.board_id)
                }}
            />

            {/* Settings Dialogs - different dialog for each source type */}
            {sourceNode.source_type === SourceType.CSV && (
                <CSVSourceDialog
                    open={showSettingsDialog}
                    onOpenChange={setShowSettingsDialog}
                    existingSource={sourceNode}
                    mode="edit"
                />
            )}

            {sourceNode.source_type === SourceType.JSON && (
                <JSONSourceDialog
                    open={showSettingsDialog}
                    onOpenChange={setShowSettingsDialog}
                    existingSource={sourceNode}
                    mode="edit"
                />
            )}

            {sourceNode.source_type === SourceType.EXCEL && (
                <ExcelSourceDialog
                    open={showSettingsDialog}
                    onOpenChange={setShowSettingsDialog}
                    existingSource={sourceNode}
                    mode="edit"
                />
            )}

            {sourceNode.source_type === SourceType.MANUAL && (
                <ManualSourceDialog
                    open={showSettingsDialog}
                    onOpenChange={setShowSettingsDialog}
                    existingSource={sourceNode}
                    mode="edit"
                />
            )}

            {sourceNode.source_type === SourceType.DATABASE && (
                <DatabaseSourceDialog
                    open={showSettingsDialog}
                    onOpenChange={setShowSettingsDialog}
                    existingSource={sourceNode}
                    mode="edit"
                />
            )}

            {/* Fallback for other source types */}
            {![SourceType.CSV, SourceType.JSON, SourceType.EXCEL, SourceType.MANUAL, SourceType.DATABASE].includes(sourceNode.source_type) && (
                <Dialog open={showSettingsDialog} onOpenChange={setShowSettingsDialog}>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Настройки источника</DialogTitle>
                            <DialogDescription>
                                Конфигурация источника данных {getTitle()}
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <Label className="text-sm font-medium">Тип источника</Label>
                                    <div className="mt-1 text-sm text-muted-foreground">{typeLabel}</div>
                                </div>
                                <div>
                                    <Label className="text-sm font-medium">Конфигурация</Label>
                                    <div className="mt-1 text-sm text-muted-foreground">{getConfigSummary()}</div>
                                </div>
                            </div>
                            <div>
                                <Label className="text-sm font-medium">Детали конфигурации</Label>
                                <div className="mt-2 p-3 bg-muted rounded-md">
                                    <pre className="text-xs overflow-auto max-h-64">
                                        {JSON.stringify(sourceNode.config, null, 2)}
                                    </pre>
                                </div>
                            </div>
                            <div className="text-xs text-muted-foreground">
                                💡 Редактирование для типа {typeLabel} будет добавлено в следующих версиях
                            </div>
                        </div>
                        <div className="flex justify-end">
                            <Button onClick={() => setShowSettingsDialog(false)}>
                                Закрыть
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>
            )}
        </>
    )
})

SourceNodeCard.displayName = 'SourceNodeCard'
