/**
 * Data Preview Modal - просмотр данных DataNode
 * См. docs/DATA_NODE_SYSTEM.md
 */
import { useState, useEffect } from 'react'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Loader2, RefreshCw, Download, Table2, AlertCircle } from 'lucide-react'
import { notify } from '@/store/notificationStore'
import api from '@/services/api'

interface DataPreviewModalProps {
    isOpen: boolean
    onClose: () => void
    boardId: string
    dataNodeId: string
    dataNodeName: string
}

interface PreviewData {
    data: Record<string, any>[]
    metadata: {
        columns: string[]
        column_types: Record<string, string>
        row_count: number
        total_row_count: number
        from_cache: boolean
        execution_time_ms?: number
    }
}

export function DataPreviewModal({
    isOpen,
    onClose,
    boardId,
    dataNodeId,
    dataNodeName,
}: DataPreviewModalProps) {
    const [previewData, setPreviewData] = useState<PreviewData | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchPreview = async (forceRefresh: boolean = false) => {
        setIsLoading(true)
        setError(null)

        try {
            const response = await api.get(
                `/api/v1/boards/${boardId}/data-nodes/${dataNodeId}/preview`,
                {
                    params: { force_refresh: forceRefresh, limit: 100 },
                }
            )

            setPreviewData(response.data)
        } catch (err: any) {
            const errorMessage = err.response?.data?.detail || 'Failed to load data preview'
            setError(errorMessage)
            notify.error(errorMessage)
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        if (isOpen) {
            fetchPreview()
        } else {
            // Reset при закрытии
            setPreviewData(null)
            setError(null)
        }
    }, [isOpen, dataNodeId])

    const handleRefresh = () => {
        fetchPreview(true)
    }

    const handleDownloadCSV = () => {
        if (!previewData) return

        const { data, metadata } = previewData
        const { columns } = metadata

        // Создаем CSV
        const csvRows = []

        // Header
        csvRows.push(columns.join(','))

        // Data rows
        for (const row of data) {
            const values = columns.map(col => {
                const val = row[col]
                // Escape запятые и кавычки
                if (val === null || val === undefined) return ''
                const str = String(val)
                if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                    return `"${str.replace(/"/g, '""')}"`
                }
                return str
            })
            csvRows.push(values.join(','))
        }

        // Скачиваем
        const csvContent = csvRows.join('\n')
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
        const link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = `${dataNodeName.replace(/[^a-z0-9]/gi, '_')}_preview.csv`
        link.click()
        URL.revokeObjectURL(link.href)

        notify.success('CSV downloaded')
    }

    const getTypeColor = (type: string): string => {
        const typeMap: Record<string, string> = {
            integer: 'bg-blue-500',
            float: 'bg-cyan-500',
            string: 'bg-gray-500',
            boolean: 'bg-green-500',
            array: 'bg-purple-500',
            object: 'bg-orange-500',
        }
        return typeMap[type] || 'bg-gray-400'
    }

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-6xl h-[80vh] flex flex-col">
                <DialogHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <DialogTitle>Data Preview: {dataNodeName}</DialogTitle>
                            <DialogDescription>
                                {previewData && (
                                    <span className="text-sm">
                                        Showing {previewData.metadata.row_count} of{' '}
                                        {previewData.metadata.total_row_count} rows
                                        {previewData.metadata.from_cache && (
                                            <Badge variant="outline" className="ml-2">
                                                Cached
                                            </Badge>
                                        )}
                                        {previewData.metadata.execution_time_ms && (
                                            <span className="ml-2 text-muted-foreground">
                                                ({previewData.metadata.execution_time_ms}ms)
                                            </span>
                                        )}
                                    </span>
                                )}
                            </DialogDescription>
                        </div>
                        <div className="flex gap-2">
                            {previewData && (
                                <>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleRefresh}
                                        disabled={isLoading}
                                    >
                                        <RefreshCw className="w-4 h-4 mr-1" />
                                        Refresh
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleDownloadCSV}
                                    >
                                        <Download className="w-4 h-4 mr-1" />
                                        CSV
                                    </Button>
                                </>
                            )}
                        </div>
                    </div>
                </DialogHeader>

                <div className="flex-1 overflow-hidden flex flex-col">
                    {isLoading ? (
                        <div className="flex items-center justify-center h-full">
                            <Loader2 className="w-8 h-8 animate-spin text-primary" />
                            <span className="ml-2">Loading data...</span>
                        </div>
                    ) : error ? (
                        <div className="flex items-center justify-center h-full text-destructive">
                            <AlertCircle className="w-8 h-8 mr-2" />
                            <div>
                                <p className="font-semibold">Error loading data</p>
                                <p className="text-sm">{error}</p>
                            </div>
                        </div>
                    ) : previewData ? (
                        <>
                            {/* Schema Info */}
                            <div className="mb-3 p-3 bg-muted/50 rounded-lg">
                                <div className="flex items-center gap-2 mb-2">
                                    <Table2 className="w-4 h-4" />
                                    <span className="font-semibold text-sm">Schema</span>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {previewData.metadata.columns.map((col) => {
                                        const type = previewData.metadata.column_types[col] || 'unknown'
                                        return (
                                            <Badge
                                                key={col}
                                                variant="secondary"
                                                className="text-xs"
                                            >
                                                <span className="font-mono">{col}</span>
                                                <span
                                                    className={`ml-1 px-1 rounded text-white ${getTypeColor(
                                                        type
                                                    )}`}
                                                >
                                                    {type}
                                                </span>
                                            </Badge>
                                        )
                                    })}
                                </div>
                            </div>

                            {/* Data Table */}
                            <div className="flex-1 overflow-auto border rounded-lg">
                                <table className="w-full text-sm">
                                    <thead className="bg-muted sticky top-0 z-10">
                                        <tr>
                                            <th className="px-3 py-2 text-left font-semibold border-b w-12">
                                                #
                                            </th>
                                            {previewData.metadata.columns.map((col) => (
                                                <th
                                                    key={col}
                                                    className="px-3 py-2 text-left font-semibold border-b"
                                                >
                                                    {col}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {previewData.data.map((row, idx) => (
                                            <tr
                                                key={idx}
                                                className="hover:bg-muted/50 border-b last:border-0"
                                            >
                                                <td className="px-3 py-2 text-muted-foreground">
                                                    {idx + 1}
                                                </td>
                                                {previewData.metadata.columns.map((col) => (
                                                    <td key={col} className="px-3 py-2 font-mono text-xs">
                                                        {renderCellValue(row[col])}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </>
                    ) : null}
                </div>
            </DialogContent>
        </Dialog>
    )
}

// Helper для рендера значений ячеек
function renderCellValue(value: any): React.ReactNode {
    if (value === null || value === undefined) {
        return <span className="text-muted-foreground italic">null</span>
    }
    if (typeof value === 'object') {
        return <span className="text-muted-foreground">{JSON.stringify(value)}</span>
    }
    if (typeof value === 'boolean') {
        return <Badge variant={value ? 'default' : 'secondary'}>{String(value)}</Badge>
    }
    return String(value)
}
