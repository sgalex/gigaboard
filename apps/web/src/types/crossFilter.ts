/**
 * Cross-Filter System TypeScript types.
 * See docs/CROSS_FILTER_SYSTEM.md
 */

// ── Filter Operators & Conditions ──────────────────────────────────

export type FilterOperator =
    | '=='
    | '!='
    | '>'
    | '<'
    | '>='
    | '<='
    | 'in'
    | 'not_in'
    | 'between'
    | 'contains'
    | 'starts_with'

export type FilterValue = string | number | boolean | string[] | number[] | [number, number] | null

export interface FilterCondition {
    type: 'condition'
    dim: string
    op: FilterOperator
    value: FilterValue
    /** Widget node ID that added this condition (for highlight mode and mini-filter). */
    initiatorWidgetId?: string
    /** Content node ID of the initiator widget — для запроса полных данных по initiator_content_node_ids. */
    initiatorContentNodeId?: string
}

export interface FilterGroup {
    type: 'and' | 'or'
    conditions: FilterExpression[]
}

export type FilterExpression = FilterCondition | FilterGroup

// ── Dimensions ─────────────────────────────────────────────────────

export type DimensionType = 'string' | 'number' | 'date' | 'boolean'

export interface Dimension {
    id: string
    project_id: string
    name: string
    display_name: string
    dim_type: DimensionType
    description: string | null
    known_values: { values: any[] } | null
    created_at: string
    updated_at: string
}

export interface DimensionCreate {
    name: string
    display_name: string
    dim_type?: DimensionType
    description?: string
    known_values?: { values: any[] } | null
}

export interface DimensionUpdate {
    display_name?: string
    dim_type?: DimensionType
    description?: string
    known_values?: { values: any[] } | null
}

// ── Column Mappings ────────────────────────────────────────────────

export type MappingSource = 'manual' | 'auto_detected' | 'ai_suggested'

export interface DimensionColumnMapping {
    id: string
    dimension_id: string
    node_id: string
    table_name: string
    column_name: string
    mapping_source: MappingSource
    confidence: number
    dim_name: string  // enriched from Dimension join
    created_at?: string
}

export interface DimensionColumnMappingCreate {
    dimension_id: string
    node_id: string
    table_name: string
    column_name: string
    mapping_source?: MappingSource
    confidence?: number
}

// ── Filter Presets ─────────────────────────────────────────────────

export type FilterPresetScope = 'project' | 'board' | 'dashboard'

export interface FilterPreset {
    id: string
    project_id: string
    name: string
    description: string | null
    filters: FilterExpression
    scope: FilterPresetScope
    target_id: string | null
    is_default: boolean
    tags: string[]
    created_by: string
    created_at: string
    updated_at: string
}

export interface FilterPresetCreate {
    name: string
    description?: string
    filters: FilterExpression
    scope?: FilterPresetScope
    target_id?: string
    is_default?: boolean
    tags?: string[]
}

export interface FilterPresetUpdate {
    name?: string
    description?: string
    filters?: FilterExpression
    is_default?: boolean
    tags?: string[]
}

// ── Active Filters ─────────────────────────────────────────────────

export interface ActiveFiltersResponse {
    filters: FilterExpression | null
    preset_id: string | null
    updated_at: string | null
}

// ── Filter Stats ───────────────────────────────────────────────────

export interface TableFilterStats {
    table_name: string
    total_rows: number
    filtered_rows: number
    percentage: number
}

// ── Dimension Detection ────────────────────────────────────────────

export interface DimensionSuggestion {
    column_name: string
    table_name: string
    suggested_name: string
    suggested_display_name: string
    suggested_type: DimensionType
    unique_count: number
    sample_values: any[]
    confidence: number
    existing_dimension_id: string | null
}

// ── Helper: extract flat conditions from expression ────────────────

export function flattenConditions(expr: FilterExpression | null): FilterCondition[] {
    if (!expr) return []
    if (expr.type === 'condition') return [expr]
    return expr.conditions.flatMap(c => flattenConditions(c))
}

/**
 * Apply active filters to a copy of tables (filter rows by condition dim == value).
 * Used to build "filtered subset" for the widget so it can compare full vs filtered and derive highlight without activeFilters.
 */
export function applyFiltersToTables(
    fullTables: Array<{ name: string; columns?: { name: string }[]; rows: Record<string, unknown>[] }>,
    activeFilters: FilterExpression | null
): Array<{ name: string; columns?: { name: string }[]; rows: Record<string, unknown>[] }> {
    const conditions = flattenConditions(activeFilters).filter((c) => c.op === '==')
    if (conditions.length === 0) return fullTables
    return fullTables.map((t) => {
        const colNames = t.columns?.map((c) => c.name) ?? (t.rows[0] ? Object.keys(t.rows[0]) : [])
        const applicable = conditions.filter((c) => colNames.includes(c.dim))
        if (applicable.length === 0) return t
        const rows = t.rows.filter((row) => applicable.every((c) => row[c.dim] == c.value))
        return { ...t, rows }
    })
}

/**
 * Build a simple AND-group from flat conditions, or return null if empty.
 */
export function buildAndGroup(conditions: FilterCondition[]): FilterExpression | null {
    if (conditions.length === 0) return null
    if (conditions.length === 1) return conditions[0]
    return { type: 'and', conditions }
}

/**
 * Human-readable label for a filter operator.
 */
export function operatorLabel(op: FilterOperator): string {
    const labels: Record<FilterOperator, string> = {
        '==': '=',
        '!=': '≠',
        '>': '>',
        '<': '<',
        '>=': '≥',
        '<=': '≤',
        in: 'в',
        not_in: 'не в',
        between: 'между',
        contains: 'содержит',
        starts_with: 'начинается с',
    }
    return labels[op] || op
}

/** Имена измерений (поле `dim`), участвующие в активном кросс-фильтре. */
export function activeFilterDimensions(expr: FilterExpression | null): Set<string> {
    return new Set(flattenConditions(expr).map((c) => c.dim))
}

/**
 * Есть ли у таблицы поле, сопоставленное с измерением из активного фильтра (nodeMappings).
 * См. DimensionColumnMapping: node_id, table_name, column_name, dim_name.
 */
export function isTableAffectedByCrossFilter(
    table: { name: string; columns?: { name: string }[]; rows?: Record<string, unknown>[] },
    activeDims: Set<string>,
    nodeMappings: DimensionColumnMapping[] | undefined
): boolean {
    if (!activeDims.size) return false
    const colNames = new Set<string>()
    for (const c of table.columns ?? []) {
        if (c?.name) colNames.add(c.name)
    }
    if (colNames.size === 0 && table.rows?.[0]) {
        for (const k of Object.keys(table.rows[0])) colNames.add(k)
    }
    for (const m of nodeMappings ?? []) {
        if (!activeDims.has(m.dim_name)) continue
        const tableOk = !m.table_name || m.table_name === table.name
        const colOk = colNames.has(m.column_name)
        if (tableOk && colOk) return true
    }
    return false
}

/**
 * Encode FilterExpression for use as URL query parameter.
 */
export function encodeFilters(expr: FilterExpression | null): string | undefined {
    if (!expr) return undefined
    return encodeURIComponent(JSON.stringify(expr))
}
