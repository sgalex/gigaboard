/**
 * Унификация строк таблиц для UI: LLM/structurizer часто отдаёт rows как массив массивов,
 * а предпросмотр ожидает объекты { [columnName]: value }. См. structurizer._add_row_ids.
 */

function formatCell(v: unknown): string {
    if (v == null) return ''
    if (typeof v === 'object') return JSON.stringify(v)
    return String(v)
}

/**
 * Строит массив значений ячеек в порядке columnNames для одной строки.
 */
export function rowToCellStrings(row: unknown, columnNames: string[]): string[] {
    if (!columnNames.length) return []
    if (Array.isArray(row)) {
        return columnNames.map((_, i) => formatCell((row as unknown[])[i]))
    }
    if (row && typeof row === 'object') {
        const o = row as Record<string, unknown>
        return columnNames.map((name) => {
            if (name in o) return formatCell(o[name])
            const hit = Object.keys(o).find((k) => k.trim() === name.trim())
            if (hit !== undefined) return formatCell(o[hit])
            return ''
        })
    }
    if (typeof row === 'string') {
        return [formatCell(row), ...columnNames.slice(1).map(() => '')]
    }
    return columnNames.map(() => '')
}

export function buildPreviewRowsMatrix(
    rawRows: unknown[] | undefined,
    columnNames: string[],
    maxRows = 100
): string[][] {
    const rows = Array.isArray(rawRows) ? rawRows.slice(0, maxRows) : []
    return rows.map((row) => rowToCellStrings(row, columnNames))
}
