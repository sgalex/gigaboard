import { memo, useCallback, useState } from 'react'
import { Handle, Position, NodeProps } from '@xyflow/react'
import { Database, Table, FileJson, Workflow, MoreVertical } from 'lucide-react'
import { DataNode, DataSourceType } from '@/types'
import { DataNodeContextMenu } from './DataNodeContextMenu'
import { DataPreviewModal } from '@/components/dialogs/DataPreviewModal'
import { Button } from '@/components/ui/button'
import { useBoardStore } from '@/store/boardStore'
import { useParams } from 'react-router-dom'

const SOURCE_ICONS = {
    [DataSourceType.SQL_QUERY]: Database,
    [DataSourceType.API_CALL]: Workflow,
    [DataSourceType.CSV_UPLOAD]: Table,
    [DataSourceType.JSON_UPLOAD]: FileJson,
    [DataSourceType.WEB_SCRAPING]: Workflow,
    [DataSourceType.FILE_SYSTEM]: Table,
    [DataSourceType.STREAMING]: Workflow,
}

const SOURCE_LABELS = {
    [DataSourceType.SQL_QUERY]: 'SQL Query',
    [DataSourceType.API_CALL]: 'API Call',
    [DataSourceType.CSV_UPLOAD]: 'CSV Upload',
    [DataSourceType.JSON_UPLOAD]: 'JSON Upload',
    [DataSourceType.WEB_SCRAPING]: 'Web Scraping',
    [DataSourceType.FILE_SYSTEM]: 'File System',
    [DataSourceType.STREAMING]: 'Streaming',
}

// Helper function to get display label based on data_node_type
const getDisplayLabel = (node: DataNode): string => {
    // Use data_node_type discriminator (new format)
    switch (node.data_node_type) {
        case 'text':
            return 'Простой текст'
        case 'api':
            return 'API'
        case 'file':
            // For files, show the file type if available
            const fileNode = node as any  // Type assertion to access file_type
            if (fileNode.file_type) {
                return fileNode.file_type.toUpperCase()
            }
            return 'Файл'
        default:
            return 'Данные'
    }
}

export const DataNodeCard = memo(({ data, selected }: NodeProps) => {
    const node = data.dataNode as DataNode
    const Icon = SOURCE_ICONS[node.data_source_type] || Database
    const label = getDisplayLabel(node)

    const { boardId } = useParams<{ boardId: string }>()
    const { deleteDataNode } = useBoardStore()

    // State для preview modal
    const [isPreviewOpen, setIsPreviewOpen] = useState(false)

    // Count rows in data
    const rowCount = node.data?.rows?.length || 0
    const columnCount = node.schema ? Object.keys(node.schema).length : 0

    const handleCreateVisualization = useCallback(() => {
        console.log('🎨 Create visualization for:', node.name)
        // TODO: Implement visualization creation dialog
        alert('Создание визуализации будет реализовано в следующей версии.\nReporter Agent сгенерирует HTML/CSS/JS код для виджета.')
    }, [node])

    const handleCreateTransformation = useCallback(() => {
        console.log('⚙️ Create transformation for:', node.name)
        // TODO: Implement transformation creation dialog
        alert('Создание трансформации будет реализовано в следующей версии.\nTransformation Agent сгенерирует Python код для обработки данных.')
    }, [node])

    const handleAddComment = useCallback(() => {
        console.log('💬 Add comment to:', node.name)
        // TODO: Implement comment creation dialog
        alert('Добавление комментария будет реализовано в следующей версии.\nМожно запросить AI-инсайты у Analyst Agent.')
    }, [node])

    const handleRefresh = useCallback(() => {
        console.log('🔄 Refresh data for:', node.name)
        // TODO: Implement data refresh
        alert('Обновление данных будет реализовано в следующей версии.\nПерезагрузит данные из источника (SQL/API/File).')
    }, [node])

    const handleEdit = useCallback(() => {
        console.log('✏️ Edit:', node.name)
        // TODO: Implement edit dialog
        alert('Редактирование узла будет реализовано в следующей версии.')
    }, [node])

    const handleDelete = useCallback(async () => {
        if (!boardId) return

        const confirmed = window.confirm(
            `Удалить узел "${node.name}"?\n\nЭто также удалит все связанные:\n- Визуализации\n- Комментарии\n- Зависимые трансформации`
        )

        if (confirmed) {
            await deleteDataNode(boardId, node.id)
        }
    }, [boardId, node, deleteDataNode])

    const handleViewData = useCallback(() => {
        console.log('👁️ View data for:', node.name)
        setIsPreviewOpen(true)
    }, [node])

    const handleExport = useCallback((format: 'csv' | 'json' | 'xlsx') => {
        console.log(`📤 Export ${node.name} as ${format}`)
        // TODO: Implement export
        alert(`Экспорт в ${format.toUpperCase()} будет реализован в следующей версии.`)
    }, [node])

    const handleViewConnections = useCallback(() => {
        console.log('🔗 View connections for:', node.name)
        // TODO: Implement connections viewer
        alert('Просмотр связей будет реализован в следующей версии.\nПоказывает все входящие и исходящие edges.')
    }, [node])

    return (
        <div
            className="bg-background border-2 border-blue-500 rounded-lg shadow-lg min-w-[240px] max-w-[320px]"
            style={{
                boxShadow: selected
                    ? '0 0 0 4px rgba(59, 130, 246, 0.6), 0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                    : undefined,
            }}
        >
            {/* Header */}
            <div className="bg-blue-500 text-white px-3 py-2 rounded-t-md flex items-center gap-2">
                <Icon className="h-4 w-4 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate" title={node.name}>
                        {node.name}
                    </div>
                    <div className="text-xs opacity-80 truncate" title={label}>
                        {label}
                    </div>
                </div>
                <DataNodeContextMenu
                    dataNode={node}
                    onCreateVisualization={handleCreateVisualization}
                    onCreateTransformation={handleCreateTransformation}
                    onAddComment={handleAddComment}
                    onRefresh={handleRefresh}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                    onViewData={handleViewData}
                    onExport={handleExport}
                    onViewConnections={handleViewConnections}
                >
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 hover:bg-blue-600"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <MoreVertical className="h-4 w-4" />
                    </Button>
                </DataNodeContextMenu>
            </div>

            {/* Content */}
            <div className="p-3 space-y-2">
                {/* Description */}
                {node.description && (
                    <div className="text-sm text-muted-foreground">
                        {node.description}
                    </div>
                )}

                {/* Data info */}
                <div className="flex gap-3 text-xs text-muted-foreground">
                    {columnCount > 0 && (
                        <div className="flex items-center gap-1">
                            <Table className="h-3 w-3" />
                            <span>{columnCount} cols</span>
                        </div>
                    )}
                    {rowCount > 0 && (
                        <div className="flex items-center gap-1">
                            <Database className="h-3 w-3" />
                            <span>{rowCount} rows</span>
                        </div>
                    )}
                </div>

                {/* Query preview */}
                {node.query && (
                    <div className="mt-2 bg-muted p-2 rounded text-xs font-mono truncate" title={node.query}>
                        {node.query}
                    </div>
                )}
            </div>

            {/* Connection handles */}
            <Handle
                type="target"
                position={Position.Left}
                style={{ width: '10px', height: '10px', backgroundColor: '#3b82f6' }}
            />
            <Handle
                type="source"
                position={Position.Right}
                style={{ width: '10px', height: '10px', backgroundColor: '#3b82f6' }}
            />

            {/* Data Preview Modal */}
            {boardId && (
                <DataPreviewModal
                    isOpen={isPreviewOpen}
                    onClose={() => setIsPreviewOpen(false)}
                    boardId={boardId}
                    dataNodeId={node.id}
                    dataNodeName={node.name}
                />
            )}
        </div>
    )
})

DataNodeCard.displayName = 'DataNodeCard'
