/**
 * Manual Source Dialog - ручной ввод данных (конструктор таблиц).
 */
import { useState } from 'react'
import { Edit3, Plus, Trash2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'

interface Column {
    name: string
    type: 'text' | 'number' | 'boolean'
}

export function ManualSourceDialog({ open, onOpenChange, initialPosition }: SourceDialogProps) {
    const [columns, setColumns] = useState<Column[]>([
        { name: 'Колонка 1', type: 'text' },
        { name: 'Колонка 2', type: 'text' },
        { name: 'Колонка 3', type: 'text' },
    ])
    const [rows, setRows] = useState<Record<string, string>[]>([
        {},
        {},
        {},
    ])

    const { isLoading, create } = useSourceDialog({
        sourceType: SourceType.MANUAL,
        onClose: () => {
            resetForm()
            onOpenChange(false)
        },
        position: initialPosition,
    })

    const resetForm = () => {
        setColumns([
            { name: 'Колонка 1', type: 'text' },
            { name: 'Колонка 2', type: 'text' },
            { name: 'Колонка 3', type: 'text' },
        ])
        setRows([{}, {}, {}])
    }

    const addColumn = () => {
        setColumns([...columns, { name: `Колонка ${columns.length + 1}`, type: 'text' }])
    }

    const removeColumn = (index: number) => {
        if (columns.length <= 1) return
        const colName = columns[index].name
        setColumns(columns.filter((_, i) => i !== index))
        setRows(rows.map(row => {
            const newRow = { ...row }
            delete newRow[colName]
            return newRow
        }))
    }

    const updateColumnName = (index: number, newName: string) => {
        const oldName = columns[index].name
        setColumns(columns.map((col, i) => i === index ? { ...col, name: newName } : col))
        // Update rows with new column name
        setRows(rows.map(row => {
            const newRow = { ...row }
            if (oldName in newRow) {
                newRow[newName] = newRow[oldName]
                delete newRow[oldName]
            }
            return newRow
        }))
    }

    const addRow = () => {
        setRows([...rows, {}])
    }

    const removeRow = (index: number) => {
        if (rows.length <= 1) return
        setRows(rows.filter((_, i) => i !== index))
    }

    const updateCell = (rowIndex: number, colName: string, value: string) => {
        setRows(rows.map((row, i) => i === rowIndex ? { ...row, [colName]: value } : row))
    }

    const handleSubmit = async () => {
        // Check if any data entered
        const hasData = rows.some(row =>
            columns.some(col => (row[col.name] || '').trim() !== '')
        )

        if (!hasData) {
            notify.error('Введите данные в таблицу')
            return
        }

        await create({
            columns: columns.map(c => ({ name: c.name, type: c.type })),
            data: rows,
        }, {
            name: 'Ручной ввод',
        })
    }

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Ручной ввод"
            description="Создайте таблицу вручную или скопируйте данные из Excel"
            icon={<Edit3 className="h-5 w-5 text-gray-500" />}
            isLoading={isLoading}
            isValid={true}
            onSubmit={handleSubmit}
        >
            <div className="space-y-4">
                {/* Toolbar */}
                <div className="flex gap-2">
                    <Button type="button" variant="outline" size="sm" onClick={addColumn}>
                        <Plus className="h-4 w-4 mr-1" />
                        Колонка
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={addRow}>
                        <Plus className="h-4 w-4 mr-1" />
                        Строка
                    </Button>
                </div>

                {/* Table */}
                <div className="border rounded-lg overflow-auto max-h-[400px]">
                    <table className="w-full text-sm">
                        <thead className="bg-muted sticky top-0">
                            <tr>
                                <th className="w-8 p-2 border-r">#</th>
                                {columns.map((col, colIndex) => (
                                    <th key={colIndex} className="p-1 border-r min-w-[120px]">
                                        <div className="flex items-center gap-1">
                                            <Input
                                                value={col.name}
                                                onChange={(e) => updateColumnName(colIndex, e.target.value)}
                                                className="h-7 text-xs font-medium"
                                            />
                                            {columns.length > 1 && (
                                                <Button
                                                    type="button"
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-6 w-6 flex-shrink-0"
                                                    onClick={() => removeColumn(colIndex)}
                                                >
                                                    <Trash2 className="h-3 w-3 text-muted-foreground" />
                                                </Button>
                                            )}
                                        </div>
                                    </th>
                                ))}
                                <th className="w-8 p-2"></th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((row, rowIndex) => (
                                <tr key={rowIndex} className="border-t">
                                    <td className="p-2 text-center text-muted-foreground border-r">
                                        {rowIndex + 1}
                                    </td>
                                    {columns.map((col, colIndex) => (
                                        <td key={colIndex} className="p-1 border-r">
                                            <Input
                                                value={row[col.name] || ''}
                                                onChange={(e) => updateCell(rowIndex, col.name, e.target.value)}
                                                className="h-7 text-xs"
                                                placeholder="..."
                                            />
                                        </td>
                                    ))}
                                    <td className="p-1">
                                        {rows.length > 1 && (
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6"
                                                onClick={() => removeRow(rowIndex)}
                                            >
                                                <Trash2 className="h-3 w-3 text-muted-foreground" />
                                            </Button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                <p className="text-xs text-muted-foreground">
                    💡 Совет: Скопируйте данные из Excel и вставьте в ячейки
                </p>
            </div>
        </BaseSourceDialog>
    )
}
