/**
 * Excel Source Dialog — интерактивный диалог для загрузки Excel файлов.
 * См. docs/SOURCE_NODE_CONCEPT_V2.md - раздел "📗 3. Excel Dialog"
 *
 * Новый UX-концепт:
 * 1. Пользователь загружает файл (drag & drop)
 * 2. Файл открывается в виде таблицы (spreadsheet grid) с ячейками
 * 3. Пользователь выделяет зоны с таблицами мышью (click+drag)
 * 4. Кнопка «Умный поиск» автоматически находит таблицы и подсвечивает их
 * 5. Найденные таблицы отображаются в предпросмотре через табы
 * 6. Пользователь может корректировать зоны и создать источник
 */
import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import {
    FileSpreadsheet, Upload, X, Loader2, Sparkles, ChevronLeft, ChevronRight, Pencil,
} from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { filesAPI } from '@/services/api'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'

// ─── Types ────────────────────────────────────────────────────────────

interface SheetCellData {
    name: string
    max_row: number
    max_col: number
    cells: (string | number | null)[][]
    visible_rows: number
    visible_cols: number
}

interface TableRegion {
    id: string
    sheetName: string
    startRow: number  // 1-based
    startCol: number  // 1-based
    endRow: number    // 1-based inclusive
    endCol: number    // 1-based inclusive
    headerRow: number | null  // 1-based
    tableName: string
    colorIndex: number
    columnOverrides?: Record<number, string>  // colIndex (0-based) -> custom name
}

interface RegionPreview {
    columns: Array<{ name: string; type: string }>
    rows: Array<Record<string, any>>
    rowCount: number
}

// ─── Constants ────────────────────────────────────────────────────────

const REGION_COLORS = [
    { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6' },
    { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981' },
    { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b' },
    { bg: 'rgba(168, 85, 247, 0.15)', border: '#a855f7' },
    { bg: 'rgba(236, 72, 153, 0.15)', border: '#ec4899' },
    { bg: 'rgba(6, 182, 212, 0.15)', border: '#06b6d4' },
]

// ─── Helpers ──────────────────────────────────────────────────────────

function colToLetter(col: number): string {
    let result = ''
    let n = col
    while (n > 0) {
        const rem = (n - 1) % 26
        result = String.fromCharCode(65 + rem) + result
        n = Math.floor((n - 1) / 26)
    }
    return result
}

function regionRangeStr(r: TableRegion): string {
    return `${colToLetter(r.startCol)}${r.startRow}:${colToLetter(r.endCol)}${r.endRow}`
}

/** Auto-detect header row: if first row is mostly text and next row has numbers */
function autoDetectHeader(
    cells: (string | number | null)[][],
    startRow: number, startCol: number, endRow: number, endCol: number,
): number | null {
    if (startRow >= endRow) return null
    const rIdx = startRow - 1
    if (rIdx < 0 || rIdx >= cells.length) return null

    let firstTextCount = 0, firstNonNull = 0
    let secondNumCount = 0, secondNonNull = 0

    for (let c = startCol; c <= endCol; c++) {
        const val1 = cells[rIdx]?.[c - 1]
        if (val1 != null) {
            firstNonNull++
            if (typeof val1 === 'string') firstTextCount++
        }
        const val2 = cells[rIdx + 1]?.[c - 1]
        if (val2 != null) {
            secondNonNull++
            if (typeof val2 === 'number') secondNumCount++
        }
    }

    if (firstNonNull === 0) return null
    const textRatio = firstTextCount / firstNonNull
    const numRatio = secondNonNull > 0 ? secondNumCount / secondNonNull : 0
    if (textRatio >= 0.6 && (numRatio > 0.3 || textRatio > 0.8)) return startRow
    return null
}

/** Extract preview data from cells for a given region */
function extractRegionPreview(
    cells: (string | number | null)[][],
    region: TableRegion,
): RegionPreview {
    const { startRow, startCol, endRow, endCol, headerRow } = region

    const columns: Array<{ name: string; type: string }> = []
    if (headerRow) {
        for (let c = startCol; c <= endCol; c++) {
            const ci = c - startCol
            const override = region.columnOverrides?.[ci]
            const val = cells[headerRow - 1]?.[c - 1]
            columns.push({ name: override ?? (val != null ? String(val) : colToLetter(c)), type: 'текст' })
        }
    } else {
        for (let c = startCol; c <= endCol; c++) {
            const ci = c - startCol
            const override = region.columnOverrides?.[ci]
            columns.push({ name: override ?? colToLetter(c), type: 'текст' })
        }
    }

    const dataStart = headerRow ? headerRow + 1 : startRow
    const rows: Array<Record<string, any>> = []
    for (let r = dataStart; r <= endRow && rows.length < 50; r++) {
        const rowDict: Record<string, any> = {}
        for (let ci = 0; ci < columns.length; ci++) {
            const c = startCol + ci
            rowDict[columns[ci].name] = cells[r - 1]?.[c - 1] ?? null
        }
        rows.push(rowDict)
    }

    for (let ci = 0; ci < columns.length; ci++) {
        let numCount = 0, textCount = 0, dateCount = 0
        for (const row of rows.slice(0, 15)) {
            const val = row[columns[ci].name]
            if (val == null) continue
            if (typeof val === 'number') numCount++
            else if (typeof val === 'string' && /^\d{4}-\d{2}/.test(val)) dateCount++
            else textCount++
        }
        const total = numCount + textCount + dateCount
        if (total === 0) columns[ci].type = 'текст'
        else if (numCount / total >= 0.5) columns[ci].type = 'число'
        else if (dateCount / total >= 0.5) columns[ci].type = 'дата'
        else columns[ci].type = 'текст'
    }

    const rowCount = Math.max(endRow - dataStart + 1, 0)
    return { columns, rows, rowCount }
}

let _regionIdCounter = 0
function nextRegionId(): string {
    return `region_${++_regionIdCounter}_${Date.now()}`
}

// ─── SpreadsheetGrid Component ────────────────────────────────────────────

function SpreadsheetGrid({
    sheet,
    regions,
    activeRegionId,
    selectionRect,
    isDragging,
    onCellMouseDown,
    onCellMouseMove,
    onCellMouseUp,
    onRegionClick,
    className,
}: {
    sheet: SheetCellData
    regions: TableRegion[]
    activeRegionId: string | null
    selectionRect: { startRow: number; startCol: number; endRow: number; endCol: number } | null
    isDragging: boolean
    onCellMouseDown: (row: number, col: number) => void
    onCellMouseMove: (row: number, col: number) => void
    onCellMouseUp: () => void
    onRegionClick: (regionId: string) => void
    className?: string
}) {
    // Map: "row-col" -> region info (for quick lookup during render)
    const cellInfo = useMemo(() => {
        const map: Record<string, { regionId: string; colorIndex: number; borderTop: boolean; borderBottom: boolean; borderLeft: boolean; borderRight: boolean }> = {}
        for (const region of regions) {
            if (region.sheetName !== sheet.name) continue
            for (let r = region.startRow; r <= Math.min(region.endRow, sheet.visible_rows); r++) {
                for (let c = region.startCol; c <= Math.min(region.endCol, sheet.visible_cols); c++) {
                    map[`${r}-${c}`] = {
                        regionId: region.id,
                        colorIndex: region.colorIndex,
                        borderTop: r === region.startRow,
                        borderBottom: r === region.endRow,
                        borderLeft: c === region.startCol,
                        borderRight: c === region.endCol,
                    }
                }
            }
        }
        return map
    }, [regions, sheet.name, sheet.visible_rows, sheet.visible_cols])

    const isInSelection = (row: number, col: number): boolean => {
        if (!selectionRect) return false
        return row >= selectionRect.startRow && row <= selectionRect.endRow &&
            col >= selectionRect.startCol && col <= selectionRect.endCol
    }

    // ─── Auto-scroll during drag ────────────────────────────────────────
    const containerRef = useRef<HTMLDivElement>(null)
    const mousePos = useRef<{ x: number; y: number } | null>(null)
    const scrollTimer = useRef<number | null>(null)

    const EDGE_ZONE = 40    // px from edge to trigger scroll
    const SCROLL_SPEED = 8  // px per frame

    useEffect(() => {
        if (!isDragging) {
            if (scrollTimer.current) { cancelAnimationFrame(scrollTimer.current); scrollTimer.current = null }
            mousePos.current = null
            return
        }

        const handleGlobalMouseMove = (e: MouseEvent) => {
            mousePos.current = { x: e.clientX, y: e.clientY }

            // Also fire cell detection so selection extends beyond visible area
            const el = containerRef.current
            if (!el) return
            const table = el.querySelector('table')
            if (!table) return
            const tbody = table.querySelector('tbody')
            if (!tbody) return
            const rows = tbody.querySelectorAll('tr')
            if (!rows.length) return

            const rect = el.getBoundingClientRect()
            const relX = e.clientX - rect.left + el.scrollLeft
            const relY = e.clientY - rect.top + el.scrollTop

            // Determine cell from coordinates
            const firstRow = rows[0]
            const cells = firstRow.querySelectorAll('td')
            if (cells.length < 2) return

            // Find column: skip first cell (row number)
            let col = 1
            for (let i = 1; i < cells.length; i++) {
                const td = cells[i] as HTMLElement
                if (relX >= td.offsetLeft + td.offsetWidth) col = i + 1
                else { col = i; break }
            }
            col = Math.max(1, Math.min(col, sheet.visible_cols))

            // Find row
            let row = 1
            for (let i = 0; i < rows.length; i++) {
                const tr = rows[i] as HTMLElement
                if (relY >= tr.offsetTop + tr.offsetHeight) row = i + 2
                else { row = i + 1; break }
            }
            row = Math.max(1, Math.min(row, sheet.cells.length))

            onCellMouseMove(row, col)
        }

        const handleGlobalMouseUp = () => {
            onCellMouseUp()
        }

        document.addEventListener('mousemove', handleGlobalMouseMove)
        document.addEventListener('mouseup', handleGlobalMouseUp)

        const tick = () => {
            const el = containerRef.current
            const pos = mousePos.current
            if (el && pos) {
                const rect = el.getBoundingClientRect()
                let dx = 0, dy = 0

                if (pos.x < rect.left + EDGE_ZONE) dx = -SCROLL_SPEED
                else if (pos.x > rect.right - EDGE_ZONE) dx = SCROLL_SPEED

                if (pos.y < rect.top + EDGE_ZONE) dy = -SCROLL_SPEED
                else if (pos.y > rect.bottom - EDGE_ZONE) dy = SCROLL_SPEED

                if (dx || dy) el.scrollBy(dx, dy)
            }
            scrollTimer.current = requestAnimationFrame(tick)
        }
        scrollTimer.current = requestAnimationFrame(tick)

        return () => {
            document.removeEventListener('mousemove', handleGlobalMouseMove)
            document.removeEventListener('mouseup', handleGlobalMouseUp)
            if (scrollTimer.current) { cancelAnimationFrame(scrollTimer.current); scrollTimer.current = null }
        }
    }, [isDragging, onCellMouseMove, onCellMouseUp, sheet.visible_cols, sheet.cells.length])

    return (
        <div
            ref={containerRef}
            className={`overflow-auto border border-border rounded-lg bg-background select-none ${className || ''}`}
            onMouseUp={onCellMouseUp}
        >
            <table className="text-[11px] border-collapse" style={{ minWidth: sheet.visible_cols * 72 }}>
                <thead className="sticky top-0 z-10">
                    <tr>
                        <th className="w-9 min-w-9 p-0.5 border border-border bg-muted text-center text-muted-foreground text-[10px] sticky left-0 z-20" />
                        {Array.from({ length: sheet.visible_cols }, (_, i) => (
                            <th key={i} className="min-w-[72px] p-0.5 border border-border bg-muted text-center text-muted-foreground font-normal text-[10px]">
                                {colToLetter(i + 1)}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {sheet.cells.map((row, rIdx) => {
                        const r1 = rIdx + 1
                        return (
                            <tr key={rIdx}>
                                <td className="p-0.5 border border-border bg-muted text-center text-muted-foreground text-[10px] font-mono sticky left-0 z-10">
                                    {r1}
                                </td>
                                {row.map((val, cIdx) => {
                                    const c1 = cIdx + 1
                                    const key = `${r1}-${c1}`
                                    const info = cellInfo[key]
                                    const inSel = isInSelection(r1, c1)
                                    const color = info ? REGION_COLORS[info.colorIndex % REGION_COLORS.length] : null
                                    const isActive = info != null && info.regionId === activeRegionId

                                    const style: React.CSSProperties = {}
                                    if (color && !inSel) {
                                        style.backgroundColor = color.bg
                                    }
                                    if (info && color) {
                                        if (info.borderTop) style.borderTop = `2px solid ${color.border}`
                                        if (info.borderBottom) style.borderBottom = `2px solid ${color.border}`
                                        if (info.borderLeft) style.borderLeft = `2px solid ${color.border}`
                                        if (info.borderRight) style.borderRight = `2px solid ${color.border}`
                                    }
                                    if (isActive && color) {
                                        style.boxShadow = `inset 0 0 0 1px ${color.border}`
                                    }

                                    return (
                                        <td
                                            key={cIdx}
                                            className={`p-0.5 px-1 border border-border/50 truncate max-w-[100px] cursor-crosshair ${inSel ? 'bg-blue-300/30 dark:bg-blue-700/30' : ''}`}
                                            style={style}
                                            onMouseDown={(e) => {
                                                e.preventDefault()
                                                if (info) onRegionClick(info.regionId)
                                                onCellMouseDown(r1, c1)
                                            }}
                                            onMouseMove={() => onCellMouseMove(r1, c1)}
                                            title={val != null ? String(val) : ''}
                                        >
                                            {val != null ? String(val) : ''}
                                        </td>
                                    )
                                })}
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}

// ─── Main Dialog ──────────────────────────────────────────────────────

export function ExcelSourceDialog({
    open,
    onOpenChange,
    initialPosition,
    existingSource,
    mode = 'create',
}: SourceDialogProps) {
    const [file, setFile] = useState<File | null>(null)
    const [fileId, setFileId] = useState<string | null>(null)
    const [isUploading, setIsUploading] = useState(false)
    const [isDetecting, setIsDetecting] = useState(false)

    // Spreadsheet cells
    const [sheetsData, setSheetsData] = useState<SheetCellData[]>([])
    const [activeSheet, setActiveSheet] = useState<string>('')

    // Regions
    const [regions, setRegions] = useState<TableRegion[]>([])
    const [activeRegionId, setActiveRegionId] = useState<string | null>(null)
    const [nextColorIndex, setNextColorIndex] = useState(0)

    // Mouse selection
    const [selStart, setSelStart] = useState<{ row: number; col: number } | null>(null)
    const [selEnd, setSelEnd] = useState<{ row: number; col: number } | null>(null)
    const [isDragging, setIsDragging] = useState(false)

    // Preview
    const [previewRegionId, setPreviewRegionId] = useState<string>('')
    const [editingRegionId, setEditingRegionId] = useState<string | null>(null)
    const [editingColumnIdx, setEditingColumnIdx] = useState<number | null>(null)

    // Settings
    const [autoDetect, setAutoDetect] = useState(true)
    const [maxRows, setMaxRows] = useState<string>('')

    const { isLoading, create, update } = useSourceDialog({
        sourceType: SourceType.EXCEL,
        onClose: () => {
            resetForm()
            onOpenChange(false)
        },
        position: initialPosition,
    })

    // ─── Edit mode init ───────────────────────────────────────────────────
    useEffect(() => {
        if (mode === 'edit' && existingSource && open) {
            const config = existingSource.config
            setFileId(config.file_id)
            setMaxRows(config.max_rows ? String(config.max_rows) : '')

            if (config.detected_regions?.length > 0) {
                const reconstructed: TableRegion[] = config.detected_regions.map((r: any, i: number) => ({
                    id: nextRegionId(),
                    sheetName: r.sheet_name,
                    startRow: r.start_row,
                    startCol: r.start_col,
                    endRow: r.end_row,
                    endCol: r.end_col,
                    headerRow: r.header_row,
                    tableName: r.table_name || `Таблица ${i + 1}`,
                    colorIndex: i,
                    columnOverrides: r.column_overrides || {},
                }))
                setRegions(reconstructed)
                setNextColorIndex(reconstructed.length)
                if (reconstructed.length > 0) {
                    setPreviewRegionId(reconstructed[0].id)
                    setActiveSheet(reconstructed[0].sheetName)
                }
            }

            if (config.file_id) loadPreview(config.file_id)
        }
    }, [mode, existingSource, open])

    const resetForm = () => {
        setFile(null)
        setFileId(null)
        setSheetsData([])
        setActiveSheet('')
        setRegions([])
        setActiveRegionId(null)
        setNextColorIndex(0)
        setSelStart(null)
        setSelEnd(null)
        setIsDragging(false)
        setPreviewRegionId('')
    }

    // ─── File handling ─────────────────────────────────────────────────────
    const handleFileDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        const droppedFile = e.dataTransfer.files[0]
        if (droppedFile && /\.xlsx?$/i.test(droppedFile.name)) {
            setFile(droppedFile)
            uploadFile(droppedFile)
        } else {
            notify.error('Только Excel файлы (.xlsx, .xls)')
        }
    }, [autoDetect])

    const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const f = e.target.files?.[0]
        if (f) {
            setFile(f)
            uploadFile(f)
        }
    }, [autoDetect])

    const uploadFile = async (f: File) => {
        setIsUploading(true)
        try {
            notify.info('Загрузка файла...')
            const uploadRes = await filesAPI.upload(f)
            const fid = uploadRes.data.file_id
            setFileId(fid)
            await loadPreview(fid)
            if (autoDetect) {
                await runSmartDetect(fid)
            }
        } catch (error) {
            notify.error('Ошибка загрузки файла')
            console.error('Excel upload error:', error)
        } finally {
            setIsUploading(false)
        }
    }

    const loadPreview = async (fid: string) => {
        const res = await filesAPI.excelPreview(fid)
        const sheets = res.data.sheets
        setSheetsData(sheets)
        if (sheets.length > 0 && !activeSheet) setActiveSheet(sheets[0].name)
    }

    // ─── Smart detect ──────────────────────────────────────────────────────
    const runSmartDetect = async (fid?: string) => {
        const id = fid || fileId
        if (!id) return
        setIsDetecting(true)
        try {
            notify.info('Умный поиск таблиц...')
            const res = await filesAPI.analyzeExcelSmart(id, true)
            const data = res.data

            const newRegions: TableRegion[] = []
            let colorIdx = 0
            for (const sheet of data.sheets) {
                for (const r of sheet.regions) {
                    newRegions.push({
                        id: nextRegionId(),
                        sheetName: r.sheet_name,
                        startRow: r.start_row,
                        startCol: r.start_col,
                        endRow: r.end_row,
                        endCol: r.end_col,
                        headerRow: r.header_row,
                        tableName: r.table_name,
                        colorIndex: colorIdx++,
                    })
                }
            }

            setRegions(newRegions)
            setNextColorIndex(colorIdx)
            if (newRegions.length > 0) {
                setPreviewRegionId(newRegions[0].id)
                setActiveRegionId(newRegions[0].id)
                setActiveSheet(newRegions[0].sheetName)
            }

            const method = data.detection_method === 'ai' ? 'AI'
                : data.detection_method === 'hybrid' ? 'Эвристика + AI' : 'Эвристика'
            notify.success(`Найдено ${data.total_tables_found} таблиц (${method})`)
        } catch (error) {
            notify.error('Ошибка умного поиска')
            console.error('Smart detect error:', error)
        } finally {
            setIsDetecting(false)
        }
    }

    // ─── Mouse selection ───────────────────────────────────────────────────
    const onCellMouseDown = useCallback((row: number, col: number) => {
        setSelStart({ row, col })
        setSelEnd({ row, col })
        setIsDragging(true)
    }, [])

    const onCellMouseMove = useCallback((row: number, col: number) => {
        if (!isDragging) return
        setSelEnd({ row, col })
    }, [isDragging])

    const onCellMouseUp = useCallback(() => {
        if (!isDragging || !selStart || !selEnd) {
            setIsDragging(false)
            return
        }
        const r1 = Math.min(selStart.row, selEnd.row)
        const c1 = Math.min(selStart.col, selEnd.col)
        const r2 = Math.max(selStart.row, selEnd.row)
        const c2 = Math.max(selStart.col, selEnd.col)

        if (r1 !== r2 || c1 !== c2) {
            const currentSheetName = activeSheet || sheetsData[0]?.name || ''
            const sheetCells = sheetsData.find(s => s.name === currentSheetName)
            const headerRow = sheetCells
                ? autoDetectHeader(sheetCells.cells, r1, c1, r2, c2)
                : null

            const newRegion: TableRegion = {
                id: nextRegionId(),
                sheetName: currentSheetName,
                startRow: r1,
                startCol: c1,
                endRow: r2,
                endCol: c2,
                headerRow,
                tableName: `Таблица ${regions.length + 1}`,
                colorIndex: nextColorIndex,
            }
            setRegions(prev => [...prev, newRegion])
            setNextColorIndex(prev => prev + 1)
            setActiveRegionId(newRegion.id)
            setPreviewRegionId(newRegion.id)
        }

        setSelStart(null)
        setSelEnd(null)
        setIsDragging(false)
    }, [isDragging, selStart, selEnd, activeSheet, sheetsData, regions.length, nextColorIndex])

    const selectionRect = useMemo(() => {
        if (!selStart || !selEnd || !isDragging) return null
        return {
            startRow: Math.min(selStart.row, selEnd.row),
            startCol: Math.min(selStart.col, selEnd.col),
            endRow: Math.max(selStart.row, selEnd.row),
            endCol: Math.max(selStart.col, selEnd.col),
        }
    }, [selStart, selEnd, isDragging])

    // ─── Region management ─────────────────────────────────────────────────
    const deleteRegion = (id: string) => {
        setRegions(prev => prev.filter(r => r.id !== id))
        if (activeRegionId === id) setActiveRegionId(null)
        if (previewRegionId === id) {
            const remaining = regions.filter(r => r.id !== id)
            setPreviewRegionId(remaining[0]?.id || '')
        }
    }

    const renameRegion = (id: string, name: string) => {
        const trimmed = name.trim()
        if (!trimmed) return
        setRegions(prev => prev.map(r => r.id === id ? { ...r, tableName: trimmed } : r))
    }

    // Focus the editing input after state change, with delay to beat Dialog focus trap
    const editStartRef = useRef(0)
    useEffect(() => {
        if (!editingRegionId) return
        editStartRef.current = Date.now()
        const timer = setTimeout(() => {
            const input = document.querySelector(`[data-edit-region="${editingRegionId}"]`) as HTMLInputElement
            if (input) { input.focus(); input.select() }
        }, 50)
        return () => clearTimeout(timer)
    }, [editingRegionId])

    const handleEditBlur = useCallback((regionId: string, value: string) => {
        // Ignore blur that fires within 100ms of edit start (caused by focus trap)
        if (Date.now() - editStartRef.current < 100) return
        renameRegion(regionId, value)
        setEditingRegionId(null)
    }, [])

    const renameColumn = useCallback((regionId: string, colIdx: number, newName: string) => {
        const trimmed = newName.trim()
        if (!trimmed) return
        setRegions(prev => prev.map(r => {
            if (r.id !== regionId) return r
            const overrides = { ...(r.columnOverrides || {}) }
            overrides[colIdx] = trimmed
            return { ...r, columnOverrides: overrides }
        }))
    }, [])

    const handleColumnEditBlur = useCallback((regionId: string, colIdx: number, value: string) => {
        if (Date.now() - editStartRef.current < 100) return
        renameColumn(regionId, colIdx, value)
        setEditingColumnIdx(null)
    }, [renameColumn])

    const startEditColumn = useCallback((colIdx: number) => {
        editStartRef.current = Date.now()
        setEditingColumnIdx(colIdx)
        setTimeout(() => {
            const input = document.querySelector(`[data-edit-column="${colIdx}"]`) as HTMLInputElement
            if (input) { input.focus(); input.select() }
        }, 50)
    }, [])

    const clearAllRegions = () => {
        setRegions([])
        setActiveRegionId(null)
        setPreviewRegionId('')
        setNextColorIndex(0)
    }

    // ─── Computed ────────────────────────────────────────────────────────
    const currentSheetData = sheetsData.find(s => s.name === activeSheet)
    const currentSheetRegions = regions.filter(r => r.sheetName === activeSheet)

    // Reset column editing when switching regions
    useEffect(() => { setEditingColumnIdx(null) }, [previewRegionId])

    const previewData = useMemo((): RegionPreview | null => {
        const region = regions.find(r => r.id === previewRegionId)
        if (!region) return null
        const sheetCells = sheetsData.find(s => s.name === region.sheetName)
        if (!sheetCells) return null
        return extractRegionPreview(sheetCells.cells, region)
    }, [previewRegionId, regions, sheetsData])

    const previewRegion = regions.find(r => r.id === previewRegionId)

    const isValid = mode === 'edit' ? regions.length > 0 : (!!file && regions.length > 0)

    const dialogTitle = mode === 'edit'
        ? `Настройки Excel — ${existingSource?.metadata?.name || 'источник'}`
        : `Excel — ${file?.name || 'загрузите файл'}`

    // ─── Submit ──────────────────────────────────────────────────────────
    const handleSubmit = async () => {
        if (regions.length === 0) {
            notify.error('Выделите хотя бы одну таблицу на листе')
            return
        }
        setIsUploading(true)
        try {
            const detectedRegions = regions.map(r => ({
                sheet_name: r.sheetName,
                start_row: r.startRow,
                start_col: r.startCol,
                end_row: r.endRow,
                end_col: r.endCol,
                header_row: r.headerRow,
                table_name: r.tableName,
                column_overrides: r.columnOverrides || {},
                selected_columns: [],
            }))

            const config: Record<string, any> = {
                file_id: fileId || existingSource?.config?.file_id,
                filename: file?.name || existingSource?.config?.filename || 'file.xlsx',
                has_header: regions.some(r => r.headerRow != null),
                analysis_mode: 'smart',
                detected_regions: detectedRegions,
            }
            if (maxRows?.trim()) config.max_rows = parseInt(maxRows, 10)

            const metadata = {
                name: file?.name?.replace(/\.xlsx?$/i, '') || existingSource?.metadata?.name || 'Excel Source',
            }

            if (mode === 'edit' && existingSource) {
                config.mime_type = existingSource.config.mime_type
                config.size_bytes = existingSource.config.size_bytes
                await update(existingSource.id, config, metadata)
            } else {
                if (!file) { notify.error('Загрузите файл'); return }
                await create(config, metadata)
                notify.success(`Источник "${file.name}" создан`)
            }
        } catch (error) {
            notify.error(mode === 'edit' ? 'Ошибка обновления' : 'Ошибка создания')
            console.error('Excel source error:', error)
        } finally {
            setIsUploading(false)
        }
    }

    // ─── Render ──────────────────────────────────────────────────────────
    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title={dialogTitle}
            description="Выделите области с таблицами слева, результат появится справа"
            icon={<FileSpreadsheet className="h-5 w-5 text-emerald-600" />}
            isLoading={isLoading || isUploading}
            isValid={isValid}
            onSubmit={handleSubmit}
            submitLabel={mode === 'edit' ? 'Сохранить' : 'Создать'}
            className="w-[calc(100vw-2rem)] max-w-[calc(100vw-2rem)] h-[calc(100vh-2rem)]"
            contentClassName="overflow-hidden"
        >
            <div className="flex-1 min-h-0 flex flex-col gap-3 overflow-hidden">
                {/* ═══ Upload zone (before file loaded) ═══ */}
                {!file && mode === 'create' && (
                    <>
                        <div
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={handleFileDrop}
                            className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-emerald-500/50 transition-colors cursor-pointer"
                            onClick={() => document.getElementById('excel-file-input')?.click()}
                        >
                            <Upload className="h-10 w-10 mx-auto mb-2 text-muted-foreground" />
                            <p className="text-sm font-medium mb-1">Перетащите Excel файл</p>
                            <p className="text-xs text-muted-foreground">.xlsx, .xls</p>
                            <Input id="excel-file-input" type="file" accept=".xlsx,.xls" onChange={handleFileSelect} className="hidden" />
                        </div>
                        <div className="flex items-center gap-2 px-1">
                            <Checkbox id="auto-detect" checked={autoDetect} onCheckedChange={(c: boolean) => setAutoDetect(c)} />
                            <Label htmlFor="auto-detect" className="text-xs text-muted-foreground cursor-pointer">
                                Автоматический умный поиск при загрузке
                            </Label>
                        </div>
                    </>
                )}

                {/* ═══ File info bar ═══ */}
                {(file || (mode === 'edit' && sheetsData.length > 0)) && (
                    <div className="flex items-center gap-2">
                        <div className="flex items-center gap-2 flex-1 min-w-0 p-2 bg-muted/50 rounded-lg">
                            <FileSpreadsheet className="h-4 w-4 text-emerald-600 shrink-0" />
                            <span className="text-sm font-medium truncate">
                                {file?.name || existingSource?.config?.filename || 'Excel файл'}
                            </span>
                            {file && <span className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</span>}
                            {sheetsData.length > 0 && <span className="text-xs text-muted-foreground">· {sheetsData.length} листов</span>}
                        </div>
                        <Button size="sm" variant="outline" onClick={() => runSmartDetect()} disabled={isDetecting || !fileId} className="gap-1.5 shrink-0">
                            {isDetecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                            Умный поиск
                        </Button>
                        {mode === 'create' && (
                            <Button size="sm" variant="ghost" onClick={resetForm} className="shrink-0"><X className="h-4 w-4" /></Button>
                        )}
                    </div>
                )}

                {/* Loading */}
                {(isUploading || isDetecting) && (
                    <div className="flex items-center gap-3 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                        <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                        <span className="text-sm">{isUploading ? 'Загрузка и анализ файла...' : 'Умный поиск таблиц...'}</span>
                    </div>
                )}

                {/* ═══ Two-panel layout ═══ */}
                {sheetsData.length > 0 && !isUploading && (
                    <div className="flex gap-4 flex-1 min-h-0 overflow-hidden">

                        {/* ──── LEFT: Исходные данные ──── */}
                        <div className="flex-1 min-w-0 flex flex-col gap-1.5 overflow-hidden">
                            <div className="flex items-center justify-between shrink-0">
                                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Исходные данные</h3>
                                <span className="text-[10px] text-muted-foreground">Выделите область мышью</span>
                            </div>

                            {/* Sheet tabs with arrow scroll */}
                            <div className="flex items-center gap-0 border-b border-border pb-1 shrink-0">
                                <button
                                    className="p-0.5 text-muted-foreground hover:text-foreground shrink-0 disabled:opacity-30"
                                    onClick={() => {
                                        const el = document.getElementById('sheet-tabs-scroll')
                                        if (el) el.scrollBy({ left: -120, behavior: 'smooth' })
                                    }}
                                >
                                    <ChevronLeft className="h-4 w-4" />
                                </button>
                                <div id="sheet-tabs-scroll" className="flex items-center gap-1 overflow-hidden flex-1 min-w-0">
                                    {sheetsData.map((s) => (
                                        <button
                                            key={s.name}
                                            onClick={() => setActiveSheet(s.name)}
                                            className={`px-2.5 py-1 text-xs font-medium rounded-t-md whitespace-nowrap transition-colors ${activeSheet === s.name
                                                    ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-b-0 border-emerald-500/30'
                                                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                                                }`}
                                        >
                                            {s.name}
                                            <span className="ml-1 text-[10px] opacity-60">({s.max_row}×{s.max_col})</span>
                                        </button>
                                    ))}
                                </div>
                                <button
                                    className="p-0.5 text-muted-foreground hover:text-foreground shrink-0 disabled:opacity-30"
                                    onClick={() => {
                                        const el = document.getElementById('sheet-tabs-scroll')
                                        if (el) el.scrollBy({ left: 120, behavior: 'smooth' })
                                    }}
                                >
                                    <ChevronRight className="h-4 w-4" />
                                </button>
                            </div>

                            {/* Spreadsheet grid — fills available space */}
                            <div className="flex-1 min-h-0 relative">
                                {currentSheetData && (
                                    <SpreadsheetGrid
                                        sheet={currentSheetData}
                                        regions={currentSheetRegions}
                                        activeRegionId={activeRegionId}
                                        selectionRect={selectionRect}
                                        isDragging={isDragging}
                                        onCellMouseDown={onCellMouseDown}
                                        onCellMouseMove={onCellMouseMove}
                                        onCellMouseUp={onCellMouseUp}
                                        onRegionClick={(id) => { setActiveRegionId(id); setPreviewRegionId(id) }}
                                        className="absolute inset-0"
                                    />
                                )}
                            </div>

                            {/* Region chips */}
                            {regions.length > 0 && (
                                <div className="flex items-center gap-1.5 flex-wrap pt-1.5 shrink-0 max-h-16 overflow-y-auto">
                                    {regions.map((r) => {
                                        const color = REGION_COLORS[r.colorIndex % REGION_COLORS.length]
                                        const preview = (() => {
                                            const s = sheetsData.find(s => s.name === r.sheetName)
                                            if (!s) return null
                                            return extractRegionPreview(s.cells, r)
                                        })()
                                        return (
                                            <div
                                                key={r.id}
                                                className={`group/chip flex items-center gap-1 pl-1.5 pr-0.5 py-0.5 rounded text-[11px] border transition-all cursor-pointer ${activeRegionId === r.id ? 'border-foreground/30 bg-muted/70' : 'border-border hover:bg-muted/40'
                                                    }`}
                                                onClick={() => { setActiveRegionId(r.id); setPreviewRegionId(r.id); setActiveSheet(r.sheetName) }}
                                            >
                                                <div className="w-2 h-2 rounded-sm shrink-0" style={{ backgroundColor: color.border }} />
                                                {editingRegionId === r.id ? (
                                                    <input
                                                        data-edit-region={r.id}
                                                        className="font-medium bg-transparent border-b border-foreground/30 outline-none text-[11px] w-24 px-0"
                                                        defaultValue={r.tableName}
                                                        onMouseDown={(e) => e.stopPropagation()}
                                                        onClick={(e) => e.stopPropagation()}
                                                        onFocus={(e) => e.stopPropagation()}
                                                        onBlur={(e) => handleEditBlur(r.id, e.target.value)}
                                                        onKeyDown={(e) => {
                                                            if (e.key === 'Enter') { renameRegion(r.id, (e.target as HTMLInputElement).value); setEditingRegionId(null) }
                                                            if (e.key === 'Escape') setEditingRegionId(null)
                                                        }}
                                                    />
                                                ) : (
                                                    <span
                                                        className="font-medium cursor-text"
                                                        onDoubleClick={(e) => { e.stopPropagation(); setEditingRegionId(r.id) }}
                                                        title="Двойной клик — переименовать"
                                                    >
                                                        {r.tableName}
                                                    </span>
                                                )}
                                                <span className="text-muted-foreground">{regionRangeStr(r)}</span>
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); setEditingRegionId(r.id) }}
                                                    className="p-0.5 hover:bg-muted rounded opacity-0 group-hover/chip:opacity-100 transition-opacity"
                                                    title="Переименовать"
                                                >
                                                    <Pencil className="h-2.5 w-2.5 text-muted-foreground" />
                                                </button>
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); deleteRegion(r.id) }}
                                                    className="p-0.5 hover:bg-destructive/10 rounded"
                                                >
                                                    <X className="h-2.5 w-2.5 text-muted-foreground hover:text-destructive" />
                                                </button>
                                            </div>
                                        )
                                    })}
                                    <button onClick={clearAllRegions} className="text-[11px] text-muted-foreground hover:text-foreground px-1">
                                        Очистить
                                    </button>
                                </div>
                            )}

                            {/* Settings */}
                            <div className="flex items-center gap-4 pt-1 shrink-0 text-xs">
                                <div className="flex items-center gap-1.5">
                                    <Checkbox
                                        id="excel-header"
                                        checked={(() => { const r = regions.find(r => r.id === previewRegionId); return r?.headerRow != null })()}
                                        disabled={!previewRegionId}
                                        onCheckedChange={(checked: boolean) => {
                                            if (!previewRegionId) return
                                            setRegions(prev => prev.map(r => {
                                                if (r.id !== previewRegionId) return r
                                                return { ...r, headerRow: checked ? r.startRow : null }
                                            }))
                                        }}
                                    />
                                    <Label htmlFor="excel-header" className="text-xs cursor-pointer">Заголовки в первой строке</Label>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    <Label htmlFor="excel-maxrows" className="text-xs text-muted-foreground">Макс.&nbsp;строк:</Label>
                                    <Input
                                        id="excel-maxrows" type="number" value={maxRows}
                                        onChange={(e) => setMaxRows(e.target.value)}
                                        placeholder="∞" min="1" className="h-6 w-16 text-xs"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* ──── RIGHT: Результат ──── */}
                        <div className="flex-1 min-w-0 flex flex-col gap-1.5 border-l border-border pl-4 overflow-hidden">
                            <div className="flex items-center justify-between shrink-0">
                                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                    Результат
                                    {regions.length > 0 && (
                                        <span className="ml-1.5 text-foreground font-bold">{regions.length}</span>
                                    )}
                                </h3>
                            </div>

                            {regions.length > 0 ? (
                                <div className="flex-1 min-h-0 flex flex-col border border-border rounded-lg overflow-hidden">
                                    {/* Region tabs */}
                                    <div className="flex items-center border-b bg-muted/30 shrink-0">
                                        <button
                                            className="shrink-0 p-1 text-muted-foreground hover:text-foreground"
                                            onClick={() => document.getElementById('region-tabs-scroll')?.scrollBy({ left: -120, behavior: 'smooth' })}
                                        >
                                            <ChevronLeft className="w-3.5 h-3.5" />
                                        </button>
                                        <div id="region-tabs-scroll" className="flex items-center gap-0.5 p-1 overflow-hidden flex-1 min-w-0">
                                            {regions.map((r) => {
                                                const color = REGION_COLORS[r.colorIndex % REGION_COLORS.length]
                                                const preview = (() => {
                                                    const s = sheetsData.find(s => s.name === r.sheetName)
                                                    if (!s) return null
                                                    return extractRegionPreview(s.cells, r)
                                                })()
                                                return (
                                                    <button
                                                        key={r.id}
                                                        onClick={() => { setPreviewRegionId(r.id); setActiveRegionId(r.id); setActiveSheet(r.sheetName) }}
                                                        className={`flex items-center gap-1.5 px-2 py-1 rounded text-[11px] whitespace-nowrap transition-colors ${previewRegionId === r.id
                                                                ? 'bg-background shadow-sm text-foreground font-medium'
                                                                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                                                            }`}
                                                    >
                                                        <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: color.border }} />
                                                        {editingRegionId === r.id ? (
                                                            <input
                                                                data-edit-region={r.id}
                                                                className="font-medium bg-transparent border-b border-foreground/30 outline-none text-[11px] w-20 px-0"
                                                                defaultValue={r.tableName}
                                                                onMouseDown={(e) => e.stopPropagation()}
                                                                onClick={(e) => e.stopPropagation()}
                                                                onFocus={(e) => e.stopPropagation()}
                                                                onBlur={(e) => handleEditBlur(r.id, e.target.value)}
                                                                onKeyDown={(e) => {
                                                                    if (e.key === 'Enter') { renameRegion(r.id, (e.target as HTMLInputElement).value); setEditingRegionId(null) }
                                                                    if (e.key === 'Escape') setEditingRegionId(null)
                                                                }}
                                                            />
                                                        ) : (
                                                            <span onDoubleClick={(e) => { e.stopPropagation(); setEditingRegionId(r.id) }}>
                                                                {r.tableName}
                                                            </span>
                                                        )}
                                                        {preview && <span className="text-[10px] opacity-60">({preview.rowCount})</span>}
                                                    </button>
                                                )
                                            })}
                                        </div>
                                        <button
                                            className="shrink-0 p-1 text-muted-foreground hover:text-foreground"
                                            onClick={() => document.getElementById('region-tabs-scroll')?.scrollBy({ left: 120, behavior: 'smooth' })}
                                        >
                                            <ChevronRight className="w-3.5 h-3.5" />
                                        </button>
                                    </div>

                                    {/* Column info */}
                                    {previewData && previewRegion && (
                                        <div className="flex items-center gap-2 px-2 py-1 border-b bg-muted/10 text-[10px] text-muted-foreground shrink-0">
                                            <span>{previewData.columns.length} колонок</span>
                                            <span>·</span>
                                            <span>{previewData.rowCount} строк</span>
                                            <span>·</span>
                                            <span>{regionRangeStr(previewRegion)}</span>
                                        </div>
                                    )}

                                    {/* Preview table */}
                                    {previewData && previewRegion ? (
                                        <div className="flex-1 min-h-0 overflow-auto">
                                            <table className="w-full text-[11px]">
                                                <thead className="bg-muted/50 sticky top-0 z-10">
                                                    <tr>
                                                        <th className="p-1 pl-2 text-left text-muted-foreground font-normal border-b w-8">#</th>
                                                        {previewData.columns.map((col, colIdx) => (
                                                            <th key={colIdx} className="p-1 text-left font-medium border-b whitespace-nowrap group/col">
                                                                {editingColumnIdx === colIdx && previewRegionId ? (
                                                                    <input
                                                                        data-edit-column={colIdx}
                                                                        className="font-medium bg-transparent border-b border-foreground/30 outline-none text-[11px] w-20 px-0"
                                                                        defaultValue={col.name}
                                                                        onMouseDown={(e) => e.stopPropagation()}
                                                                        onClick={(e) => e.stopPropagation()}
                                                                        onFocus={(e) => e.stopPropagation()}
                                                                        onBlur={(e) => handleColumnEditBlur(previewRegionId, colIdx, e.target.value)}
                                                                        onKeyDown={(e) => {
                                                                            if (e.key === 'Enter') { renameColumn(previewRegionId, colIdx, (e.target as HTMLInputElement).value); setEditingColumnIdx(null) }
                                                                            if (e.key === 'Escape') setEditingColumnIdx(null)
                                                                            if (e.key === 'Tab') {
                                                                                e.preventDefault()
                                                                                renameColumn(previewRegionId, colIdx, (e.target as HTMLInputElement).value)
                                                                                const nextIdx = e.shiftKey ? colIdx - 1 : colIdx + 1
                                                                                if (nextIdx >= 0 && nextIdx < previewData.columns.length) startEditColumn(nextIdx)
                                                                                else setEditingColumnIdx(null)
                                                                            }
                                                                        }}
                                                                    />
                                                                ) : (
                                                                    <span
                                                                        className="cursor-text hover:text-primary"
                                                                        onDoubleClick={() => startEditColumn(colIdx)}
                                                                        title="Двойной клик — переименовать"
                                                                    >
                                                                        {col.name}
                                                                    </span>
                                                                )}
                                                                <span className="ml-1 text-[9px] text-muted-foreground font-normal">{col.type}</span>
                                                            </th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {previewData.rows.slice(0, 30).map((row, idx) => (
                                                        <tr key={idx} className="border-b border-border/30 hover:bg-muted/20">
                                                            <td className="p-1 pl-2 text-muted-foreground tabular-nums">{idx + 1}</td>
                                                            {previewData.columns.map((col) => (
                                                                <td key={col.name} className="p-1 truncate max-w-[120px]">
                                                                    {row[col.name] != null ? String(row[col.name]) : <span className="text-muted-foreground/50">—</span>}
                                                                </td>
                                                            ))}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    ) : (
                                        <div className="flex-1 flex items-center justify-center">
                                            <p className="text-xs text-muted-foreground">Выберите таблицу</p>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="flex-1 flex flex-col items-center justify-center border border-dashed border-border rounded-lg">
                                    <FileSpreadsheet className="h-8 w-8 text-muted-foreground/30 mb-2" />
                                    <p className="text-sm text-muted-foreground">Нет выделенных таблиц</p>
                                    <p className="text-xs text-muted-foreground/70 mt-1">Выделите область на листе слева<br />или нажмите «Умный поиск»</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </BaseSourceDialog>
    )
}
