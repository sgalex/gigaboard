/**
 * Manual Source Dialog — полноценный конструктор таблиц с ручным вводом.
 *
 * Фичи:
 * - Несколько таблиц (табы + добавление)
 * - Типы столбцов: текст, число, дата
 * - Inline редактирование ячеек
 * - Вставка из буфера обмена (Excel/Google Sheets)
 * - Редактируемое имя ноды
 * - Удаление строк и столбцов
 *
 * См. docs/SOURCE_NODE_CONCEPT.md — раздел "✏️ 8. Manual Input Dialog"
 */
import { useState, useCallback, useRef, useEffect, KeyboardEvent, ClipboardEvent } from 'react'
import { Edit3, Plus, Trash2, Clipboard, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'

// ─── Types ──────────────────────────────────────────────

type ColumnType = 'text' | 'number' | 'date'

interface Column {
    id: string
    name: string
    type: ColumnType
}

interface TableDef {
    id: string
    name: string
    columns: Column[]
    rows: Record<string, string>[]
}

const COLUMN_TYPE_LABELS: Record<ColumnType, string> = {
    text: 'Текст',
    number: 'Число',
    date: 'Дата',
}

// ─── Helpers ────────────────────────────────────────────

let colIdCounter = 0
function nextColId() {
    return `col_${++colIdCounter}_${Date.now()}`
}

let tableIdCounter = 0
function nextTableId() {
    return `table_${++tableIdCounter}_${Date.now()}`
}

function makeDefaultColumns(count = 3): Column[] {
    return Array.from({ length: count }, (_, i) => ({
        id: nextColId(),
        name: `Колонка ${i + 1}`,
        type: 'text' as ColumnType,
    }))
}

function makeEmptyRows(count = 3): Record<string, string>[] {
    return Array.from({ length: count }, () => ({}))
}

function makeDefaultTable(index = 1): TableDef {
    return {
        id: nextTableId(),
        name: `Таблица ${index}`,
        columns: makeDefaultColumns(),
        rows: makeEmptyRows(),
    }
}

/**
 * Parse clipboard text (tab-separated from Excel/Sheets) into columns + rows.
 */
function parseClipboard(text: string): { columns: string[]; rows: string[][] } | null {
    const lines = text.trim().split('\n').filter(l => l.length > 0)
    if (lines.length === 0) return null

    const delimiter = lines[0].includes('\t') ? '\t' : ','
    const parsed = lines.map(line => line.split(delimiter).map(cell => cell.trim()))

    if (parsed.length < 1) return null

    // First row as headers
    const columns = parsed[0]
    const rows = parsed.slice(1)

    return { columns, rows }
}

/**
 * Guess column type from values.
 */
function guessColumnType(values: string[]): ColumnType {
    const nonEmpty = values.filter(v => v.length > 0)
    if (nonEmpty.length === 0) return 'text'

    // Check if all are numbers
    const allNumbers = nonEmpty.every(v => !isNaN(Number(v.replace(',', '.'))) && v.trim() !== '')
    if (allNumbers) return 'number'

    // Check if all look like dates (YYYY-MM-DD, DD.MM.YYYY, etc.)
    const datePatterns = [
        /^\d{4}-\d{2}-\d{2}$/,
        /^\d{2}\.\d{2}\.\d{4}$/,
        /^\d{2}\/\d{2}\/\d{4}$/,
    ]
    const allDates = nonEmpty.every(v => datePatterns.some(p => p.test(v)))
    if (allDates) return 'date'

    return 'text'
}

// ─── Hydrate from existing source ───────────────────────

/**
 * Convert existing SourceNode config/content into internal TableDef[] state.
 * Supports both new format (config.tables) and legacy format (config.columns + config.data).
 * Also falls back to content.tables when config has no table data.
 */
function hydrateTables(existingSource: any): TableDef[] {
    const config = existingSource?.config || {}
    const content = existingSource?.content || {}

    // Prefer config.tables (new format from this dialog)
    let sourceTables: any[] = config.tables || []

    // Fallback: legacy format with columns + data
    if (sourceTables.length === 0 && config.columns) {
        sourceTables = [{
            name: config.table_name || 'Таблица 1',
            columns: config.columns,
            rows: config.data || [],
        }]
    }

    // Fallback: content.tables (saved by extraction)
    if (sourceTables.length === 0 && content.tables?.length > 0) {
        sourceTables = content.tables
    }

    if (sourceTables.length === 0) {
        return [makeDefaultTable(1)]
    }

    return sourceTables.map((t: any, idx: number) => {
        const columns: Column[] = (t.columns || []).map((c: any) => ({
            id: nextColId(),
            name: c.name || `Колонка ${idx + 1}`,
            type: (['text', 'number', 'date'].includes(c.type) ? c.type : 'text') as ColumnType,
        }))

        // Build rows keyed by column.id
        const rows: Record<string, string>[] = (t.rows || []).map((row: any) => {
            const obj: Record<string, string> = {}
            columns.forEach((col, ci) => {
                // row may be keyed by column name
                const origColName = (t.columns || [])[ci]?.name
                const val = origColName != null ? row[origColName] : undefined
                obj[col.id] = val != null ? String(val) : ''
            })
            return obj
        })

        return {
            id: nextTableId(),
            name: t.name || `Таблица ${idx + 1}`,
            columns,
            rows: rows.length > 0 ? rows : makeEmptyRows(1),
        } as TableDef
    })
}

// ─── Component ──────────────────────────────────────────

export function ManualSourceDialog({ open, onOpenChange, initialPosition, existingSource, mode = 'create' }: SourceDialogProps) {
    const isEditMode = mode === 'edit' && !!existingSource

    const [nodeName, setNodeName] = useState('Ручной ввод')
    const [tables, setTables] = useState<TableDef[]>(() => [makeDefaultTable(1)])
    const [activeTableId, setActiveTableId] = useState('')
    const [editingTabId, setEditingTabId] = useState<string | null>(null)
    const [editingTabName, setEditingTabName] = useState('')
    const [showClipboard, setShowClipboard] = useState(false)
    const [clipboardText, setClipboardText] = useState('')

    const tabNameInputRef = useRef<HTMLInputElement>(null)

    const { isLoading, create, update } = useSourceDialog({
        sourceType: SourceType.MANUAL,
        onClose: () => {
            if (!isEditMode) resetForm()
            onOpenChange(false)
        },
        position: initialPosition,
    })

    // Load existing source data when opening in edit mode
    useEffect(() => {
        if (isEditMode && open) {
            const name = existingSource?.metadata?.name
                || existingSource?.node_metadata?.name
                || 'Ручной ввод'
            setNodeName(name)

            const hydrated = hydrateTables(existingSource)
            setTables(hydrated)
            setActiveTableId(hydrated[0]?.id || '')
            setShowClipboard(false)
            setClipboardText('')
        }
    }, [isEditMode, existingSource, open])

    // Initialize activeTableId from first table
    useEffect(() => {
        if (tables.length > 0 && !tables.find(t => t.id === activeTableId)) {
            setActiveTableId(tables[0].id)
        }
    }, [tables, activeTableId])

    // Focus tab rename input when editing
    useEffect(() => {
        if (editingTabId && tabNameInputRef.current) {
            tabNameInputRef.current.focus()
            tabNameInputRef.current.select()
        }
    }, [editingTabId])

    const activeTable = tables.find(t => t.id === activeTableId) || tables[0]

    const resetForm = () => {
        colIdCounter = 0
        tableIdCounter = 0
        const defaultTable = makeDefaultTable(1)
        setNodeName('Ручной ввод')
        setTables([defaultTable])
        setActiveTableId(defaultTable.id)
        setEditingTabId(null)
        setShowClipboard(false)
        setClipboardText('')
    }

    // ─── Table mutations ────────────────────────────────

    const updateTable = useCallback((tableId: string, updater: (t: TableDef) => TableDef) => {
        setTables(prev => prev.map(t => t.id === tableId ? updater(t) : t))
    }, [])

    const addTable = () => {
        const newTable = makeDefaultTable(tables.length + 1)
        setTables(prev => [...prev, newTable])
        setActiveTableId(newTable.id)
    }

    const removeTable = (tableId: string) => {
        if (tables.length <= 1) {
            notify.warning('Нужна хотя бы одна таблица')
            return
        }
        const remaining = tables.filter(t => t.id !== tableId)
        setTables(remaining)
        if (activeTableId === tableId) {
            setActiveTableId(remaining[0].id)
        }
    }

    // ─── Column mutations ───────────────────────────────

    const addColumn = () => {
        updateTable(activeTable.id, t => ({
            ...t,
            columns: [...t.columns, {
                id: nextColId(),
                name: `Колонка ${t.columns.length + 1}`,
                type: 'text' as ColumnType,
            }],
        }))
    }

    const removeColumn = (colId: string) => {
        updateTable(activeTable.id, t => {
            if (t.columns.length <= 1) return t
            return {
                ...t,
                columns: t.columns.filter(c => c.id !== colId),
                rows: t.rows.map(row => {
                    const newRow = { ...row }
                    delete newRow[colId]
                    return newRow
                }),
            }
        })
    }

    const updateColumnName = (colId: string, newName: string) => {
        updateTable(activeTable.id, t => ({
            ...t,
            columns: t.columns.map(c => c.id === colId ? { ...c, name: newName } : c),
        }))
    }

    const updateColumnType = (colId: string, newType: ColumnType) => {
        updateTable(activeTable.id, t => ({
            ...t,
            columns: t.columns.map(c => c.id === colId ? { ...c, type: newType } : c),
        }))
    }

    // ─── Row mutations ──────────────────────────────────

    const addRow = () => {
        updateTable(activeTable.id, t => ({
            ...t,
            rows: [...t.rows, {}],
        }))
    }

    const removeRow = (rowIndex: number) => {
        updateTable(activeTable.id, t => {
            if (t.rows.length <= 1) return t
            return { ...t, rows: t.rows.filter((_, i) => i !== rowIndex) }
        })
    }

    const updateCell = (rowIndex: number, colId: string, value: string) => {
        updateTable(activeTable.id, t => ({
            ...t,
            rows: t.rows.map((row, i) => i === rowIndex ? { ...row, [colId]: value } : row),
        }))
    }

    // ─── Tab rename ─────────────────────────────────────

    const startEditingTab = (tableId: string) => {
        const table = tables.find(t => t.id === tableId)
        if (!table) return
        setEditingTabId(tableId)
        setEditingTabName(table.name)
    }

    const finishEditingTab = () => {
        if (editingTabId && editingTabName.trim()) {
            updateTable(editingTabId, t => ({ ...t, name: editingTabName.trim() }))
        }
        setEditingTabId(null)
        setEditingTabName('')
    }

    const handleTabKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            finishEditingTab()
        } else if (e.key === 'Escape') {
            setEditingTabId(null)
            setEditingTabName('')
        }
    }

    // ─── Clipboard paste ────────────────────────────────

    const handleClipboardImport = () => {
        if (!clipboardText.trim()) {
            notify.warning('Вставьте данные в поле')
            return
        }

        const parsed = parseClipboard(clipboardText)
        if (!parsed || parsed.columns.length === 0) {
            notify.error('Не удалось распознать данные. Попробуйте скопировать из Excel снова.')
            return
        }

        // Create columns with guessed types
        const colValues: string[][] = parsed.columns.map((_, colIdx) =>
            parsed.rows.map(row => row[colIdx] || '')
        )

        const newColumns: Column[] = parsed.columns.map((name, idx) => ({
            id: nextColId(),
            name: name || `Колонка ${idx + 1}`,
            type: guessColumnType(colValues[idx] || []),
        }))

        // Create rows keyed by column id
        const newRows: Record<string, string>[] = parsed.rows.map(row => {
            const obj: Record<string, string> = {}
            newColumns.forEach((col, idx) => {
                obj[col.id] = row[idx] || ''
            })
            return obj
        })

        // Replace active table content
        updateTable(activeTable.id, t => ({
            ...t,
            columns: newColumns,
            rows: newRows.length > 0 ? newRows : makeEmptyRows(1),
        }))

        setShowClipboard(false)
        setClipboardText('')
        notify.success(`Импортировано: ${newColumns.length} столбцов, ${newRows.length} строк`)
    }

    /**
     * Handle Ctrl+V in the table area — if a larger paste detected, show clipboard importer.
     */
    const handleTablePaste = useCallback((e: ClipboardEvent<HTMLDivElement>) => {
        const text = e.clipboardData.getData('text/plain')
        if (!text) return

        // Check if multi-line paste (from spreadsheet)
        const lines = text.trim().split('\n')
        if (lines.length > 1 || (lines.length === 1 && lines[0].includes('\t'))) {
            e.preventDefault()
            setClipboardText(text)
            setShowClipboard(true)
        }
        // Single-value paste is handled naturally by the input
    }, [])

    // ─── Keyboard navigation ────────────────────────────

    const handleCellKeyDown = (
        e: KeyboardEvent<HTMLInputElement>,
        rowIndex: number,
        colIndex: number,
    ) => {
        const { key } = e
        if (key === 'Tab') {
            e.preventDefault()
            const cols = activeTable.columns.length
            const rows = activeTable.rows.length

            let nextRow = rowIndex
            let nextCol = colIndex

            if (e.shiftKey) {
                nextCol--
                if (nextCol < 0) {
                    nextCol = cols - 1
                    nextRow--
                }
            } else {
                nextCol++
                if (nextCol >= cols) {
                    nextCol = 0
                    nextRow++
                }
                // Add new row if tabbing past last cell
                if (nextRow >= rows) {
                    addRow()
                }
            }

            if (nextRow >= 0) {
                const cellId = `cell-${activeTable.id}-${nextRow}-${nextCol}`
                setTimeout(() => {
                    const el = document.getElementById(cellId) as HTMLInputElement
                    el?.focus()
                    el?.select()
                }, 0)
            }
        } else if (key === 'Enter') {
            e.preventDefault()
            const nextRow = rowIndex + 1
            if (nextRow >= activeTable.rows.length) {
                addRow()
            }
            setTimeout(() => {
                const cellId = `cell-${activeTable.id}-${nextRow}-${colIndex}`
                const el = document.getElementById(cellId) as HTMLInputElement
                el?.focus()
                el?.select()
            }, 0)
        }
    }

    // ─── Build config from current state ─────────────────

    const buildConfig = () => {
        return tables.map(t => {
            const columns = t.columns.map(c => ({ name: c.name, type: c.type }))
            const rows = t.rows
                .filter(row => t.columns.some(col => (row[col.id] || '').trim() !== ''))
                .map(row => {
                    const obj: Record<string, any> = {}
                    t.columns.forEach(col => {
                        const raw = row[col.id] || ''
                        if (col.type === 'number' && raw.trim() !== '') {
                            const num = Number(raw.replace(',', '.'))
                            obj[col.name] = isNaN(num) ? raw : num
                        } else {
                            obj[col.name] = raw
                        }
                    })
                    return obj
                })
            return {
                name: t.name,
                columns,
                rows,
            }
        }).filter(t => t.rows.length > 0)
    }

    // ─── Submit ─────────────────────────────────────────

    const handleSubmit = async () => {
        // Validate: at least one table with some data
        const hasData = tables.some(t =>
            t.rows.some(row =>
                t.columns.some(col => (row[col.id] || '').trim() !== '')
            )
        )

        if (!hasData) {
            notify.error('Введите данные хотя бы в одну таблицу')
            return
        }

        // Build config in format expected by ManualSource extractor:
        // config.tables = [{name, columns: [{name, type}], rows: [{col_name: value}]}]
        const configTables = buildConfig()

        if (configTables.length === 0) {
            notify.error('Все таблицы пусты')
            return
        }

        const config = { tables: configTables }
        const metadata = { name: nodeName.trim() || 'Ручной ввод' }

        if (isEditMode && existingSource) {
            await update(existingSource.id, config, metadata)
        } else {
            await create(config, metadata)
        }
    }

    // ─── Render ─────────────────────────────────────────

    const totalRows = tables.reduce((acc, t) => acc + t.rows.filter(row =>
        t.columns.some(col => (row[col.id] || '').trim() !== '')
    ).length, 0)

    const dialogTitle = isEditMode
        ? `✏️ Редактирование — ${nodeName}`
        : `✏️ Ручной ввод — ${nodeName}`

    const dialogDescription = isEditMode
        ? 'Редактируйте таблицы и сохраните изменения'
        : 'Создайте таблицы вручную или вставьте данные из Excel'

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title={dialogTitle}
            description={dialogDescription}
            icon={<Edit3 className="h-5 w-5 text-gray-500" />}
            isLoading={isLoading}
            isValid={true}
            onSubmit={handleSubmit}
            submitLabel={isEditMode ? 'Сохранить' : '✏️ Создать источник'}
            className="max-w-5xl"
            contentClassName="overflow-hidden"
        >
            <div className="flex flex-col gap-3 min-h-0 flex-1">
                {/* Node name */}
                <div className="flex items-center gap-2">
                    <label className="text-xs font-medium text-muted-foreground whitespace-nowrap">
                        Название:
                    </label>
                    <Input
                        value={nodeName}
                        onChange={e => setNodeName(e.target.value)}
                        className="h-7 text-sm max-w-xs"
                        placeholder="Введите название источника"
                    />
                </div>

                {/* Table tabs */}
                <div className="flex items-center gap-1 border-b pb-1">
                    {tables.map(t => (
                        <div
                            key={t.id}
                            className={`group flex items-center gap-1 px-3 py-1 rounded-t text-xs cursor-pointer border border-b-0 transition-colors ${activeTableId === t.id
                                    ? 'bg-background border-border font-medium'
                                    : 'bg-muted/50 border-transparent hover:bg-muted text-muted-foreground'
                                }`}
                            onClick={() => setActiveTableId(t.id)}
                            onDoubleClick={() => startEditingTab(t.id)}
                        >
                            {editingTabId === t.id ? (
                                <input
                                    ref={tabNameInputRef}
                                    value={editingTabName}
                                    onChange={e => setEditingTabName(e.target.value)}
                                    onBlur={finishEditingTab}
                                    onKeyDown={handleTabKeyDown}
                                    className="h-5 w-24 text-xs px-1 bg-background border rounded"
                                    onClick={e => e.stopPropagation()}
                                />
                            ) : (
                                <span className="truncate max-w-[120px]">{t.name}</span>
                            )}
                            {tables.length > 1 && (
                                <button
                                    className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-destructive/10"
                                    onClick={e => {
                                        e.stopPropagation()
                                        removeTable(t.id)
                                    }}
                                    title="Удалить таблицу"
                                >
                                    <X className="h-3 w-3 text-muted-foreground hover:text-destructive" />
                                </button>
                            )}
                        </div>
                    ))}
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={addTable}
                        title="Добавить таблицу"
                    >
                        <Plus className="h-3.5 w-3.5" />
                    </Button>
                </div>

                {/* Toolbar */}
                <div className="flex items-center gap-2">
                    <Button type="button" variant="outline" size="sm" onClick={addColumn}>
                        <Plus className="h-3.5 w-3.5 mr-1" />
                        Столбец
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={addRow}>
                        <Plus className="h-3.5 w-3.5 mr-1" />
                        Строка
                    </Button>
                    <div className="flex-1" />
                    <Button
                        type="button"
                        variant={showClipboard ? 'secondary' : 'outline'}
                        size="sm"
                        onClick={() => setShowClipboard(!showClipboard)}
                    >
                        <Clipboard className="h-3.5 w-3.5 mr-1" />
                        Вставить из буфера
                    </Button>
                    <span className="text-xs text-muted-foreground">
                        {activeTable.columns.length} стб. × {activeTable.rows.length} стр.
                    </span>
                </div>

                {/* Clipboard importer */}
                {showClipboard && (
                    <div className="border rounded-lg p-3 bg-muted/30 space-y-2">
                        <p className="text-xs text-muted-foreground">
                            Скопируйте таблицу из Excel или Google Sheets и вставьте сюда (Ctrl+V):
                        </p>
                        <Textarea
                            value={clipboardText}
                            onChange={e => setClipboardText(e.target.value)}
                            placeholder="Вставьте данные из Excel (со заголовками)..."
                            className="min-h-[80px] text-xs font-mono"
                        />
                        <div className="flex gap-2 justify-end">
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => { setShowClipboard(false); setClipboardText('') }}
                            >
                                Отмена
                            </Button>
                            <Button
                                type="button"
                                size="sm"
                                onClick={handleClipboardImport}
                                disabled={!clipboardText.trim()}
                            >
                                Распознать
                            </Button>
                        </div>
                    </div>
                )}

                {/* Spreadsheet table */}
                <div
                    className="border rounded-lg overflow-auto flex-1 min-h-[200px] max-h-[400px]"
                    onPaste={handleTablePaste}
                >
                    <table className="w-full text-sm border-collapse">
                        <thead className="bg-muted sticky top-0 z-10">
                            <tr>
                                <th className="w-8 p-1.5 border-r text-center text-xs text-muted-foreground">
                                    #
                                </th>
                                {activeTable.columns.map((col, colIndex) => (
                                    <th key={col.id} className="p-1 border-r min-w-[140px]">
                                        <div className="flex flex-col gap-0.5">
                                            <div className="flex items-center gap-0.5">
                                                <Input
                                                    value={col.name}
                                                    onChange={e => updateColumnName(col.id, e.target.value)}
                                                    className="h-6 text-xs font-medium flex-1 min-w-0"
                                                    placeholder="Название"
                                                />
                                                {activeTable.columns.length > 1 && (
                                                    <Button
                                                        type="button"
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-5 w-5 flex-shrink-0"
                                                        onClick={() => removeColumn(col.id)}
                                                        title="Удалить столбец"
                                                    >
                                                        <Trash2 className="h-3 w-3 text-muted-foreground" />
                                                    </Button>
                                                )}
                                            </div>
                                            <Select
                                                value={col.type}
                                                onValueChange={v => updateColumnType(col.id, v as ColumnType)}
                                            >
                                                <SelectTrigger className="h-5 text-[10px] px-1.5 border-dashed">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {Object.entries(COLUMN_TYPE_LABELS).map(([val, label]) => (
                                                        <SelectItem key={val} value={val} className="text-xs">
                                                            {label}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </th>
                                ))}
                                <th className="w-8 p-1"></th>
                            </tr>
                        </thead>
                        <tbody>
                            {activeTable.rows.map((row, rowIndex) => (
                                <tr key={rowIndex} className="border-t hover:bg-muted/30">
                                    <td className="p-1.5 text-center text-xs text-muted-foreground border-r tabular-nums">
                                        {rowIndex + 1}
                                    </td>
                                    {activeTable.columns.map((col, colIndex) => (
                                        <td key={col.id} className="p-0.5 border-r">
                                            <Input
                                                id={`cell-${activeTable.id}-${rowIndex}-${colIndex}`}
                                                value={row[col.id] || ''}
                                                onChange={e => updateCell(rowIndex, col.id, e.target.value)}
                                                onKeyDown={e => handleCellKeyDown(e, rowIndex, colIndex)}
                                                className="h-7 text-xs border-0 shadow-none focus-visible:ring-1 rounded-none"
                                                placeholder="..."
                                                type={col.type === 'date' ? 'date' : 'text'}
                                                inputMode={col.type === 'number' ? 'decimal' : undefined}
                                            />
                                        </td>
                                    ))}
                                    <td className="p-0.5">
                                        {activeTable.rows.length > 1 && (
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6"
                                                onClick={() => removeRow(rowIndex)}
                                                title="Удалить строку"
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

                {/* Footer info */}
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                        💡 Tab — следующая ячейка &bull; Enter — следующая строка &bull; Ctrl+V — вставка из буфера
                    </span>
                    <span>
                        {tables.length > 1
                            ? `${tables.length} таблиц · ${totalRows} строк с данными`
                            : `${totalRows} строк с данными`}
                    </span>
                </div>
            </div>
        </BaseSourceDialog>
    )
}
