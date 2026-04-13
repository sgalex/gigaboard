import { memo, useState } from 'react'
import { useFilterStore } from '@/store/filterStore'
import { useLibraryStore } from '@/store/libraryStore'
import { Handle, Position, NodeProps } from '@xyflow/react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
    Table2,
    FileText,
    MoreVertical,
    Code,
    TrendingUp,
    Download,
    GitBranch,
    Eye,
    Settings,
    Edit2,
    RefreshCw,
    Trash2,
    Filter,
    Copy,
} from 'lucide-react'
import { ContentNode } from '@/types'
import { cn } from '@/lib/utils'
import { TransformDialog } from './TransformDialog'
import { WidgetDialog } from './WidgetDialog'
import { useBoardStore } from '@/store/boardStore'
import { notify } from '@/store/notificationStore'
import { useAuthStore } from '@/store/authStore'

interface ContentNodeCardProps extends NodeProps {
    data: {
        contentNode: ContentNode
    }
}

export const ContentNodeCard = memo(({ data, selected }: ContentNodeCardProps) => {
    const { contentNode } = data
    const [showLineage, setShowLineage] = useState(false)
    const [showPreviewModal, setShowPreviewModal] = useState(false)
    const [showTransformDialog, setShowTransformDialog] = useState(false)
    const [showWidgetDialog, setShowWidgetDialog] = useState(false)
    const [activeTableIndex, setActiveTableIndex] = useState(0)
    const [editTransformData, setEditTransformData] = useState<{
        messages: Array<{ id: string; role: string; content: string; timestamp: Date }>
        code: string
        transformationId: string
    } | null>(null)
    const [isEditingName, setIsEditingName] = useState(false)
    const [tempName, setTempName] = useState('')
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [isDuplicating, setIsDuplicating] = useState(false)

    const transformContent = useBoardStore((state) => state.transformContent)
    const visualizeContent = useBoardStore((state) => state.visualizeContent)
    const updateContentNode = useBoardStore((state) => state.updateContentNode)
    const duplicateContentNode = useBoardStore((state) => state.duplicateContentNode)
    const deleteContentNode = useBoardStore((state) => state.deleteContentNode)
    const fetchWidgetNodes = useBoardStore((state) => state.fetchWidgetNodes)
    const fetchEdges = useBoardStore((state) => state.fetchEdges)
    const edges = useBoardStore((state) => state.edges)
    const sourceNodes = useBoardStore((state) => state.sourceNodes)
    const contentNodes = useBoardStore((state) => state.contentNodes)
    const token = useAuthStore((state) => state.token)

    // Get ALL source nodes for transform dialog (supports multi-source transforms)
    const getSourceNodesForTransform = (): any[] => {
        const lineage = contentNode.lineage
        const sourceNodeIds: string[] = lineage?.source_node_ids || (lineage?.source_node_id ? [lineage.source_node_id] : [])

        if (sourceNodeIds.length === 0) return [contentNode]

        const resolved = sourceNodeIds.map(id => {
            const sn = sourceNodes.find(n => n.id === id)
            if (sn) return sn
            const cn = contentNodes.find(n => n.id === id)
            if (cn) return cn
            return null
        }).filter(Boolean)

        return resolved.length > 0 ? resolved : [contentNode]
    }

    // Handle name edit
    const handleStartEditName = () => {
        setTempName(getTitle())
        setIsEditingName(true)
    }

    const handleSaveName = async () => {
        if (tempName.trim() && tempName !== getTitle()) {
            const newMetadata = {
                ...(contentNode.metadata || {}),
                name: tempName.trim()
            }
            console.log('💾 Saving ContentNode name:', {
                nodeId: contentNode.id,
                oldName: getTitle(),
                newName: tempName.trim(),
                oldMetadata: contentNode.metadata,
                newMetadata
            })
            await updateContentNode(contentNode.id, {
                metadata: newMetadata
            })
        }
        setIsEditingName(false)
    }

    const handleCancelEditName = () => {
        setIsEditingName(false)
        setTempName('')
    }

    // Open preview with specific table
    const handleOpenTablePreview = (tableIndex: number) => {
        setActiveTableIndex(tableIndex)
        setShowPreviewModal(true)
    }

    const filteredEntry = useFilterStore((s) => s.filteredNodeData?.[contentNode.id] ?? null)
    const isFiltered = filteredEntry !== null
    const activeTables = filteredEntry?.tables ?? contentNode.content?.tables ?? []
    const tableCount = activeTables.length
    const hasText = !!contentNode.content?.text
    const totalRows = activeTables.reduce((sum: number, t: any) => sum + (t.row_count || 0), 0)

    // Handle transformation
    const handleTransform = async (code: string, transformationId: string, description?: string, chatHistory?: Array<{ role: string; content: string }>) => {
        // Pass contentNode.id as targetNodeId to UPDATE existing node instead of creating new one
        await transformContent(
            contentNode.lineage?.source_node_id || contentNode.id,  // source_node_id for API
            description || '',
            code,
            transformationId,
            contentNode.id,  // targetNodeId - UPDATE this node
            chatHistory  // Pass chat history
        )
    }

    // Handle edit transformation (open dialog with saved params)
    const handleEditTransform = async () => {
        console.log('🎯 handleEditTransform called, contentNode:', contentNode)
        const lineage = contentNode.lineage
        console.log('📊 Lineage:', lineage)
        const transformHistory = lineage?.transformation_history || []
        console.log('📜 Transform history:', transformHistory)
        let lastTransform = transformHistory[transformHistory.length - 1]
        console.log('🔍 Last transform:', lastTransform)

        // Fallback: try to load from Edge if transformation_history is empty
        if (!lastTransform && lineage?.transformation_id) {
            console.log('⚠️ No transformation_history, trying to load from Edge...')
            try {
                await fetchEdges(contentNode.board_id)
                const transformEdge = edges.find(
                    (e: any) =>
                        e.target_node_id === contentNode.id &&
                        e.edge_type === 'TRANSFORMATION'
                )

                if (transformEdge?.transformation_params) {
                    console.log('✅ Found transformation data in Edge:', transformEdge.transformation_params)
                    lastTransform = {
                        operation: 'transform',
                        description: transformEdge.label || transformEdge.transformation_params.prompt || 'Transform data',
                        code_snippet: transformEdge.transformation_params.code || '',
                        transformation_id: lineage.transformation_id,
                        timestamp: lineage.timestamp || new Date().toISOString()
                    }
                }
            } catch (error) {
                console.error('Failed to load transformation from Edge:', error)
            }
        }

        if (!lastTransform) {
            console.warn('No transformation data found, opening empty dialog')
            setEditTransformData(null)
            setShowTransformDialog(true)
            return
        }

        console.log('🔧 Opening transform dialog in edit mode:', {
            description: lastTransform.description,
            codeLength: lastTransform.code_snippet?.length || 0,
            transformationId: lastTransform.transformation_id
        })

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
            transformationId: lastTransform.transformation_id || ''
        })
        setShowTransformDialog(true)
    }

    // Handle refresh - re-execute transformation with existing code and update current node
    const handleRefresh = async () => {
        const lineage = contentNode.lineage
        const transformHistory = lineage?.transformation_history || []
        let lastTransform = transformHistory[transformHistory.length - 1]

        // Fallback: try to load from Edge if transformation_history is empty
        if (!lastTransform && lineage?.transformation_id) {
            try {
                await fetchEdges(contentNode.board_id)
                const transformEdge = edges.find(
                    (e: any) =>
                        e.target_node_id === contentNode.id &&
                        e.edge_type === 'TRANSFORMATION'
                )

                if (transformEdge?.transformation_params) {
                    lastTransform = {
                        operation: 'transform',
                        description: transformEdge.label || transformEdge.transformation_params.prompt || 'Transform data',
                        code_snippet: transformEdge.transformation_params.code || '',
                        transformation_id: lineage.transformation_id,
                        timestamp: lineage.timestamp || new Date().toISOString()
                    }
                }
            } catch (error) {
                console.error('Failed to load transformation from Edge:', error)
            }
        }

        if (!lastTransform || !lastTransform.code_snippet) {
            notify.error('Не удалось найти код трансформации для обновления')
            return
        }

        const sourceNodeId = lineage?.source_node_id
        if (!sourceNodeId) {
            notify.error('Не удалось найти исходный узел')
            return
        }

        setIsRefreshing(true)
        try {
            notify.info('Обновление данных...')

            // Execute transformation to get new data
            const response = await fetch(`/api/v1/content-nodes/${sourceNodeId}/transform/test`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({
                    code: lastTransform.code_snippet,
                    transformation_id: lastTransform.transformation_id,
                }),
            })

            if (!response.ok) {
                throw new Error('Failed to execute transformation')
            }

            const result = await response.json()

            // Update current ContentNode with new data (preserve name and text)
            await updateContentNode(contentNode.id, {
                content: {
                    text: contentNode.content?.text || '',  // Keep existing text
                    tables: result.tables || []  // Update only tables
                },
                metadata: {
                    ...contentNode.metadata,
                    execution_time_ms: result.execution_time_ms,
                    refreshed_at: new Date().toISOString()
                }
            })

            // Re-fetch dimensions and node tables — refresh may expose new columns
            const projectId = useBoardStore.getState().currentBoard?.project_id
            if (projectId) {
                useFilterStore.getState().loadDimensions(projectId)
                const boards = useBoardStore.getState().boards.filter(b => b.project_id === projectId)
                if (boards.length > 0) {
                    useLibraryStore.getState().fetchNodeTables(boards)
                }
            }

            notify.success('Данные обновлены')
        } catch (error) {
            console.error('Failed to refresh ContentNode:', error)
            notify.error('Не удалось обновить данные')
        } finally {
            setIsRefreshing(false)
        }
    }

    // Handle visualization
    const handleVisualize = async (params: {
        user_prompt?: string
        widget_name?: string
        auto_refresh?: boolean
    }) => {
        await visualizeContent(contentNode.id, params)
    }

    // Handle delete
    const handleDelete = async () => {
        if (confirm('Удалить ContentNode и все зависимые узлы?')) {
            await deleteContentNode(contentNode.id)
        }
    }

    const handleDuplicate = async () => {
        if (isDuplicating) return
        setIsDuplicating(true)
        try {
            await duplicateContentNode(contentNode)
        } finally {
            setIsDuplicating(false)
        }
    }

    // Handle export to Excel
    const handleExportToExcel = async () => {
        try {
            const XLSX = await import('xlsx')
            const workbook = XLSX.utils.book_new()

            if (tableCount === 0) {
                alert('Нет данных для экспорта')
                return
            }

            // Export each table as a separate sheet
            contentNode.content.tables.forEach((table, idx) => {
                const rawColumns = table.columns || []
                const columns = rawColumns.map((col: any) => col.name)
                const rawRows = table.rows || []
                // Dict rows: extract values in column order
                const arrayRows = rawRows.map((row: any) => {
                    return columns.map((colName: string) => row?.[colName] ?? '')
                })

                // Prepare data with headers (rows as array of arrays)
                const sheetData = [columns, ...arrayRows]
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

    // Get node title
    const getTitle = (): string => {
        // Strategic logging for ContentNode naming pipeline debugging
        console.log(`[ContentNodeCard] getTitle() for node ${contentNode.id}:`, {
            'metadata': contentNode.metadata,
            'metadata?.name': contentNode.metadata?.name,
            'node_metadata': (contentNode as any).node_metadata,
            'tables[0].name': tableCount > 0 ? contentNode.content.tables[0].name : '<no tables>',
            'full contentNode keys': Object.keys(contentNode),
        })
        if (contentNode.metadata?.name) return contentNode.metadata.name
        if (tableCount > 0) return contentNode.content.tables[0].name
        return 'Узел данных'
    }

    const getTablesSummary = (): string => {
        if (tableCount === 0) return 'No tables'
        if (tableCount === 1) {
            const table = activeTables[0]
            const rowCount = table?.row_count ?? table?.rows?.length ?? 0
            const colCount = table?.column_count ?? table?.columns?.length ?? 0
            return `${table.name} • ${rowCount} rows × ${colCount} cols`
        }
        return `${tableCount} tables • ${totalRows} total rows`
    }

    // Get lineage info
    const getLineageInfo = (): string => {
        const lineage = contentNode.lineage
        const transformCount = lineage?.transformation_history?.length || 0

        if (transformCount > 0) {
            return `${transformCount} transformation(s)`
        }
        if (lineage?.operation === 'extract') {
            return 'Extracted data'
        }
        return 'Direct extraction'
    }

    // Render table preview
    const renderTablePreview = (tableIndex: number) => {
        const table = activeTables[tableIndex]
        if (!table) return null

        // Handle column format
        const rawColumns = table.columns || []
        const columns = rawColumns.map((col: any) => col.name)

        // Handle row formats: dict rows (unified)
        const rawRows = table.rows?.slice(0, 100) || []
        const previewRows = rawRows.map((row: any) => {
            // Dict row: extract values in column order
            return columns.map((colName: string) => row?.[colName] ?? '')
        })

        return (
            <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{table.row_count ?? table.rows?.length ?? 0} rows × {columns.length} columns</span>
                </div>
                <div className="overflow-auto max-h-48 border rounded-md">
                    <table className="w-full text-xs">
                        <thead className="bg-muted sticky top-0">
                            <tr>
                                {columns.map((colName: string, idx: number) => (
                                    <th
                                        key={idx}
                                        className="px-2 py-1 text-left font-medium border-b border-r last:border-r-0"
                                    >
                                        <div className="truncate max-w-[100px]" title={colName}>
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
                                            <div className="truncate max-w-[100px]" title={String(cellValue ?? '')}>
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
                        Showing 5 of {table.row_count} rows
                    </div>
                )}
            </div>
        )
    }

    return (
        <>
            <Handle type="target" position={Position.Left} className="w-3 h-3" isConnectable={false} />

            <Card
                className={cn(
                    'w-[320px] transition-all',
                    selected && 'ring-2 ring-primary ring-offset-2'
                )}
            >
                <CardHeader className="p-3 pb-2">
                    <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                            <div className="p-2 rounded-md bg-blue-500 text-white">
                                <Table2 className="w-4 h-4" />
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
                                        className="font-semibold text-sm truncate"
                                        title={getTitle()}
                                        onDoubleClick={handleStartEditName}
                                    >
                                        {getTitle()}
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="flex items-center gap-0.5">
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="ghost" size="icon" className="h-8 w-8">
                                        <MoreVertical className="h-4 w-4" />
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                    <DropdownMenuItem onClick={handleStartEditName}>
                                        <Edit2 className="mr-2 h-4 w-4" />
                                        Переименовать
                                    </DropdownMenuItem>
                                    {tableCount > 0 && (
                                        <>
                                            <DropdownMenuSeparator />
                                            <DropdownMenuItem onClick={() => setShowPreviewModal(true)}>
                                                <Eye className="mr-2 h-4 w-4" />
                                                Просмотр таблиц
                                            </DropdownMenuItem>
                                        </>
                                    )}
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={handleEditTransform}>
                                        <Settings className="mr-2 h-4 w-4" />
                                        {contentNode.lineage?.transformation_history?.length > 0 ? "Редактировать трансформацию" : "Настройки трансформации"}
                                    </DropdownMenuItem>
                                    {contentNode.lineage?.transformation_id && (
                                        <DropdownMenuItem onClick={handleRefresh} disabled={isRefreshing}>
                                            <RefreshCw className="mr-2 h-4 w-4" />
                                            Обновить данные
                                        </DropdownMenuItem>
                                    )}
                                    <DropdownMenuItem onClick={() => setShowTransformDialog(true)}>
                                        <Code className="mr-2 h-4 w-4" />
                                        Обработка
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => setShowWidgetDialog(true)}>
                                        <TrendingUp className="mr-2 h-4 w-4" />
                                        Визуализация
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    {tableCount > 0 && (
                                        <DropdownMenuItem onClick={handleExportToExcel}>
                                            <Download className="mr-2 h-4 w-4" />
                                            Экспорт в Excel
                                        </DropdownMenuItem>
                                    )}
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={handleDuplicate} disabled={isDuplicating}>
                                        <Copy className="mr-2 h-4 w-4" />
                                        Создать копию
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
                    {/* Text section */}
                    {hasText && (
                        <div className="text-xs text-muted-foreground p-2 bg-muted rounded leading-relaxed line-clamp-3">
                            {contentNode.content.text}
                        </div>
                    )}

                    {/* Tables as clickable badges */}
                    {tableCount > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                            {isFiltered && (
                                <Filter
                                    className="w-3 h-3 text-blue-600"
                                    aria-label="Фильтр активен"
                                />
                            )}
                            {activeTables.map((table: any, idx: number) => (
                                <Badge
                                    key={idx}
                                    variant="outline"
                                    className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors text-xs"
                                    onClick={() => handleOpenTablePreview(idx)}
                                >
                                    <span className="font-medium">{table.name}</span>
                                    <span className="ml-1.5 px-1.5 py-0.5 bg-primary/10 rounded text-[10px] font-semibold">
                                        {table.row_count || 0}
                                    </span>
                                </Badge>
                            ))}
                        </div>
                    )}

                    {/* Expanded lineage view */}
                    {showLineage && contentNode.lineage && (
                        <div className="mt-2 p-2 bg-muted rounded text-xs space-y-1">
                            <div className="font-medium">Lineage:</div>
                            {contentNode.lineage.source_node_id && (
                                <div>Source: {contentNode.lineage.source_node_id.slice(0, 8)}...</div>
                            )}
                            {contentNode.lineage.parent_content_ids?.length > 0 && (
                                <div>Parents: {contentNode.lineage.parent_content_ids.length}</div>
                            )}
                            {contentNode.lineage.transformation_history?.length > 0 && (
                                <div>
                                    Transforms: {contentNode.lineage.transformation_history.length}
                                </div>
                            )}
                            {contentNode.lineage.operation && (
                                <div className="capitalize">Operation: {contentNode.lineage.operation}</div>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Right handle for transformations (horizontal connections) */}
            <Handle type="source" position={Position.Right} className="w-3 h-3" id="transform" isConnectable={false} />

            {/* Bottom handle for visualizations (vertical connections) */}
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
                        <DialogTitle>{getTitle()}</DialogTitle>
                        <DialogDescription>
                            {getTablesSummary()}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex-1 overflow-auto space-y-4">
                        {/* Text section */}
                        {hasText && (
                            <div className="text-sm text-muted-foreground p-3 bg-muted rounded leading-relaxed">
                                {contentNode.content.text}
                            </div>
                        )}

                        {/* Tables with tabs */}
                        {tableCount > 0 && (
                            <div className="space-y-3">
                                {/* Tabs */}
                                {tableCount > 1 && (
                                    <div className="flex gap-2 overflow-x-auto pb-2 border-b">
                                        {activeTables.map((table: any, idx: number) => (
                                            <button
                                                key={idx}
                                                onClick={() => setActiveTableIndex(idx)}
                                                className={cn(
                                                    'px-4 py-2 text-sm rounded-md transition-colors whitespace-nowrap flex items-center gap-2',
                                                    activeTableIndex === idx
                                                        ? 'bg-primary text-primary-foreground'
                                                        : 'bg-muted hover:bg-muted/80'
                                                )}
                                            >
                                                <span>{table.name}</span>
                                                <span className={cn(
                                                    'px-2 py-0.5 text-xs rounded-full',
                                                    activeTableIndex === idx
                                                        ? 'bg-primary-foreground/20 text-primary-foreground'
                                                        : 'bg-background/50 text-muted-foreground'
                                                )}>
                                                    {(table.row_count ?? table.rows?.length ?? 0).toLocaleString()}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                )}

                                {/* Active table preview */}
                                {renderTablePreview(activeTableIndex)}
                            </div>
                        )}
                    </div>
                </DialogContent>
            </Dialog>

            {/* Transform Dialog */}
            <TransformDialog
                open={showTransformDialog}
                onOpenChange={(open) => {
                    console.log('💬 TransformDialog onOpenChange:', {
                        open,
                        hasEditData: !!editTransformData,
                        editDataContent: editTransformData ? {
                            messagesCount: editTransformData.messages?.length,
                            codeLength: editTransformData.code?.length,
                            transformationId: editTransformData.transformationId
                        } : null
                    })
                    setShowTransformDialog(open)
                    if (!open) setEditTransformData(null) // Clear edit data on close
                }}
                sourceNodes={getSourceNodesForTransform()}
                onTransform={handleTransform}
                initialMessages={editTransformData?.messages}
                initialCode={editTransformData?.code}
                initialTransformationId={editTransformData?.transformationId}
            />

            {/* Visualize Dialog */}
            <WidgetDialog
                open={showWidgetDialog}
                onOpenChange={setShowWidgetDialog}
                contentNode={contentNode}
                onVisualize={handleVisualize}
                onWidgetCreated={async () => {
                    await fetchWidgetNodes(contentNode.board_id)
                    await fetchEdges(contentNode.board_id)
                }}
            />
        </>
    )
})

ContentNodeCard.displayName = 'ContentNodeCard'
