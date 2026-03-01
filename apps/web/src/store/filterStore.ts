/**
 * FilterStore — Zustand store for cross-filter system state.
 *
 * Manages active filters, dimensions, presets, and UI state.
 * See docs/CROSS_FILTER_SYSTEM.md §8
 */
import { create } from 'zustand'
import { dimensionsAPI, filtersAPI, filterPresetsAPI } from '@/services/api'
import { notify } from './notificationStore'
import type {
    Dimension,
    DimensionColumnMapping,
    FilterCondition,
    FilterExpression,
    FilterPreset,
    TableFilterStats,
} from '@/types/crossFilter'
import { flattenConditions, buildAndGroup, encodeFilters } from '@/types/crossFilter'

// ── Types ──────────────────────────────────────────────────────────

export type FilterContext =
    | { type: 'board'; id: string; projectId: string }
    | { type: 'dashboard'; id: string; projectId: string }
    | null

/** Пересчитанные данные нод после применения фильтров (только для отображения). */
export interface FilteredNodeEntry {
    tables: any[]
    uses_ai: boolean   // если true — данные из кэша (ai_resolve_batch)
    from_cache: boolean
}

interface FilterState {
    // Active filters
    activeFilters: FilterExpression | null
    activePresetId: string | null

    // Dimensions & mappings
    dimensions: Dimension[]
    nodeMappings: Record<string, DimensionColumnMapping[]> // nodeId → mappings
    dimMappings: Record<string, DimensionColumnMapping[]>  // dimId → mappings (for explorer UI)
    isLoadingDimMappings: Record<string, boolean>          // dimId → loading flag

    // Presets
    presets: FilterPreset[]

    // UI state
    isFilterBarVisible: boolean
    isFilterPanelOpen: boolean
    filterStats: TableFilterStats[]

    // Context (board or dashboard)
    context: FilterContext

    // Loading flags
    isLoadingDimensions: boolean
    isLoadingPresets: boolean

    // Пересчитанные данные нод (не сохраняются в БД, только для отображения). Всегда отфильтрованные — для карточек ContentNode.
    filteredNodeData: Record<string, FilteredNodeEntry> | null
    /** Полные (не отфильтрованные) данные только для initiator ContentNode — для виджета (highlight full vs filtered). */
    initiatorFullNodeData: Record<string, FilteredNodeEntry>
    isComputingFiltered: boolean

    // Content node IDs, для которых возвращать полные данные в initiatorFullNodeData — виджеты-инициаторы
    initiatorContentNodeIds: string[]

    // Стек предыдущих датасетов по виджету-инициатору (для отрисовки «предыдущее состояние + выделенный текущий»)
    dataStackByWidgetId: Record<string, Array<{ tables: any[] }>>
}

interface FilterActions {
    // Context
    setContext: (ctx: FilterContext) => void

    // Filter mutations
    setFilters: (filters: FilterExpression | null) => void
    addCondition: (condition: FilterCondition, initiatorWidgetId?: string, contentNodeId?: string) => void
    removeCondition: (dimName: string) => void

    /** Стек предыдущих датасетов для виджета-инициатора (только если виджет инициировал фильтр) */
    getDataStack: (widgetId: string) => Array<{ tables: any[] }>
    /** Виджет при клике кладёт текущие данные в стек (вызывается из оснастки по postMessage) */
    pushToDataStack: (widgetId: string, tables: any[]) => void
    clearFilters: () => void

    // Content node IDs для виджетов-инициаторов (полные данные для highlight)
    setInitiatorContentNodeIds: (ids: string[]) => void

    // Click-to-filter from widget (nodeId = contentNodeId, widgetNodeId = widget that initiated)
    handleWidgetClick: (field: string, value: any, contentNodeId: string, widgetNodeId?: string) => void
    handleWidgetToggleFilter: (dimension: string, value: any, contentNodeId: string, widgetNodeId?: string) => void
    handleWidgetRemoveFilter: (dimension: string) => void

    // Условия, добавленные конкретным виджетом (для мини-фильтра на карточке)
    getConditionsByInitiator: (widgetNodeId: string) => FilterCondition[]

    // Presets
    loadPresets: (projectId: string) => Promise<void>
    applyPreset: (presetId: string) => void
    saveAsPreset: (name: string, description?: string) => Promise<void>

    // Dimensions
    loadDimensions: (projectId: string) => Promise<void>
    loadMappingsForNode: (nodeId: string) => Promise<void>
    loadMappingsForDimension: (projectId: string, dimId: string) => Promise<void>
    deleteDimensionMapping: (projectId: string, mappingId: string, dimId: string) => Promise<void>
    createDimensionMapping: (projectId: string, dimId: string, data: {
        node_id: string; table_name: string; column_name: string
    }) => Promise<void>
    deleteDimension: (projectId: string, dimId: string) => Promise<void>
    createDimension: (projectId: string, data: { name: string; display_name?: string; dim_type?: string }) => Promise<Dimension | null>
    mergeDimensions: (projectId: string, sourceIds: string[], targetId: string) => Promise<void>

    // UI
    setFilterBarVisible: (v: boolean) => void
    setFilterPanelOpen: (v: boolean) => void
    setFilterStats: (stats: TableFilterStats[]) => void

    // Sync to backend (active filters)
    syncFiltersToBackend: () => Promise<void>

    // Пересчёт pandas-цепочки на отфильтрованных данных (без сохранения в БД)
    computeFiltered: () => Promise<void>

    // Helpers
    getFiltersQueryParam: () => string | undefined
    resolveFieldToDimension: (field: string, nodeId: string) => Dimension | null
}

type FilterStore = FilterState & FilterActions

// Debounce timer for sync
let _syncTimer: ReturnType<typeof setTimeout> | null = null
const SYNC_DEBOUNCE_MS = 300

export const useFilterStore = create<FilterStore>((set, get) => ({
    // ── Initial state ──────────────────────────────────────────────

    activeFilters: null,
    activePresetId: null,
    dimensions: [],
    nodeMappings: {},
    dimMappings: {},
    isLoadingDimMappings: {},
    presets: [],
    isFilterBarVisible: true,
    isFilterPanelOpen: false,
    filterStats: [],
    context: null,
    isLoadingDimensions: false,
    isLoadingPresets: false,
    filteredNodeData: null,
    initiatorFullNodeData: {},
    isComputingFiltered: false,
    initiatorContentNodeIds: [],
    dataStackByWidgetId: {},

    // ── Context ────────────────────────────────────────────────────

    getDataStack: (widgetId) => {
        return get().dataStackByWidgetId[widgetId] ?? []
    },

    pushToDataStack: (widgetId, tables) => {
        if (!widgetId || !Array.isArray(tables) || tables.length === 0) return
        const stack = get().dataStackByWidgetId[widgetId] ?? []
        set({
            dataStackByWidgetId: {
                ...get().dataStackByWidgetId,
                [widgetId]: [...stack, { tables: tables }],
            },
        })
    },

    setContext: (ctx) => {
        const prev = get().context
        // Reset filters when switching context
        if (
            !ctx ||
            !prev ||
            ctx.type !== prev.type ||
            ctx.id !== prev.id
        ) {
            set({
                context: ctx,
                activeFilters: null,
                activePresetId: null,
                filterStats: [],
                filteredNodeData: null,
                initiatorFullNodeData: {},
                initiatorContentNodeIds: [],
                dataStackByWidgetId: {},
            })
        } else {
            set({ context: ctx })
        }
    },

    // ── Filter mutations ───────────────────────────────────────────

    setFilters: (filters) => {
        set({ activeFilters: filters, activePresetId: null })
        get().syncFiltersToBackend()
        get().computeFiltered()
    },

    addCondition: (condition, initiatorWidgetId, contentNodeId) => {
        const { activeFilters } = get()
        const existing = flattenConditions(activeFilters)
        const withInitiator =
            initiatorWidgetId && contentNodeId
                ? { ...condition, initiatorWidgetId, initiatorContentNodeId: contentNodeId }
                : initiatorWidgetId
                  ? { ...condition, initiatorWidgetId }
                  : condition
        // Стек заполняется виджетом при вызове toggleFilter (pushCurrentDataToStack в оснастке)
        const filtered = existing.filter((c) => c.dim !== withInitiator.dim)
        filtered.push(withInitiator as FilterCondition)
        const newFilters = buildAndGroup(filtered)
        const initiatorIds = [...new Set((filtered as FilterCondition[]).map((c) => c.initiatorContentNodeId).filter(Boolean))] as string[]
        set({
            activeFilters: newFilters,
            activePresetId: null,
            initiatorContentNodeIds: initiatorIds,
        })
        get().syncFiltersToBackend()
        get().computeFiltered()
    },

    setInitiatorContentNodeIds: (ids) => set({ initiatorContentNodeIds: ids }),

    removeCondition: (dimName) => {
        const { activeFilters, dataStackByWidgetId } = get()
        const existing = flattenConditions(activeFilters)
        const removed = existing.find((c) => c.dim === dimName) as FilterCondition | undefined
        // Оснастка: при снятии фильтра убираем одну запись из стека виджета-инициатора
        let nextStack = dataStackByWidgetId
        if (removed?.initiatorWidgetId) {
            const stack = dataStackByWidgetId[removed.initiatorWidgetId]
            if (stack?.length) {
                const newStack = stack.slice(0, -1)
                nextStack = { ...dataStackByWidgetId, [removed.initiatorWidgetId]: newStack }
            }
        }
        const filtered = existing.filter((c) => c.dim !== dimName)
        const newFilters = buildAndGroup(filtered)
        const initiatorIds = [...new Set((filtered as FilterCondition[]).map((c) => c.initiatorContentNodeId).filter(Boolean))] as string[]
        set({
            activeFilters: newFilters,
            activePresetId: null,
            dataStackByWidgetId: nextStack,
            initiatorContentNodeIds: initiatorIds,
        })
        get().syncFiltersToBackend()
        get().computeFiltered()
    },

    clearFilters: () => {
        set({
            activeFilters: null,
            activePresetId: null,
            filterStats: [],
            filteredNodeData: null,
            initiatorFullNodeData: {},
            dataStackByWidgetId: {},
            initiatorContentNodeIds: [],
        })
        get().syncFiltersToBackend()
    },

    // ── Click-to-filter ────────────────────────────────────────────

    handleWidgetClick: (field, value, contentNodeId, widgetNodeId) => {
        let dimName = get().resolveFieldToDimension(field, contentNodeId)?.name

        if (!dimName) {
            const allMappings = Object.values(get().nodeMappings).flat() as any[]
            const m = allMappings.find((m) => m.column_name === field)
            if (m) dimName = m.dim_name
        }
        if (!dimName) dimName = get().dimensions.find((d) => d.name === field)?.name
        if (!dimName) dimName = field  // last resort: use column name directly

        if (!get().nodeMappings[contentNodeId]) get().loadMappingsForNode(contentNodeId)

        get().addCondition(
            { type: 'condition', dim: dimName, op: '==', value },
            widgetNodeId,
            contentNodeId,
        )
    },

    handleWidgetToggleFilter: (dimension, value, contentNodeId, widgetNodeId) => {
        // 1. Try to resolve via loaded nodeMappings
        let dimName = get().resolveFieldToDimension(dimension, contentNodeId)?.name

        // 2. Fallback: search all loaded nodeMappings for any node that has this column
        if (!dimName) {
            const allMappings = Object.values(get().nodeMappings).flat() as any[]
            const m = allMappings.find((m) => m.column_name === dimension)
            if (m) dimName = m.dim_name
        }

        // 3. Fallback: find dimension by name directly
        if (!dimName) {
            dimName = get().dimensions.find((d) => d.name === dimension)?.name
        }

        // 4. Last resort: use the column name as-is
        if (!dimName) dimName = dimension

        // Lazily load mappings for this node so future clicks resolve faster
        if (!get().nodeMappings[contentNodeId]) get().loadMappingsForNode(contentNodeId)

        const existing = flattenConditions(get().activeFilters)
        const match = existing.find((c) => c.dim === dimName && c.value === value)
        if (match) {
            get().removeCondition(dimName)
        } else {
            get().addCondition(
                { type: 'condition', dim: dimName, op: '==', value },
                widgetNodeId,
                contentNodeId,
            )
        }
    },

    getConditionsByInitiator: (widgetNodeId) => {
        const conditions = flattenConditions(get().activeFilters)
        return conditions.filter((c) => c.initiatorWidgetId === widgetNodeId)
    },

    handleWidgetRemoveFilter: (dimension) => {
        const dimName = get().dimensions.find((d) => d.name === dimension)?.name
        if (dimName) {
            get().removeCondition(dimName)
        }
    },

    // ── Presets ────────────────────────────────────────────────────

    loadPresets: async (projectId) => {
        set({ isLoadingPresets: true })
        try {
            const res = await filterPresetsAPI.list(projectId)
            set({ presets: res.data })
        } catch (e) {
            console.error('Failed to load presets', e)
        } finally {
            set({ isLoadingPresets: false })
        }
    },

    applyPreset: (presetId) => {
        const preset = get().presets.find((p) => p.id === presetId)
        if (!preset) return
        set({
            activeFilters: preset.filters,
            activePresetId: presetId,
        })
        get().syncFiltersToBackend()
        get().computeFiltered()
    },

    saveAsPreset: async (name, description) => {
        const { context, activeFilters } = get()
        if (!context || !activeFilters) return
        try {
            const data = {
                name,
                description,
                filters: activeFilters,
                scope: context.type as any,
                target_id: context.id,
            }
            await filterPresetsAPI.create(context.projectId, data)
            await get().loadPresets(context.projectId)
            notify.success(`Пресет "${name}" сохранён`)
        } catch (e) {
            console.error('Failed to save preset', e)
            notify.error('Не удалось сохранить пресет')
        }
    },

    // ── Dimensions ─────────────────────────────────────────────────

    loadDimensions: async (projectId) => {
        set({ isLoadingDimensions: true })
        try {
            const res = await dimensionsAPI.list(projectId)
            set({ dimensions: res.data })
        } catch (e) {
            console.error('Failed to load dimensions', e)
        } finally {
            set({ isLoadingDimensions: false })
        }
    },

    loadMappingsForNode: async (nodeId) => {
        try {
            const res = await dimensionsAPI.getMappingsForNode(nodeId)
            set((state) => ({
                nodeMappings: {
                    ...state.nodeMappings,
                    [nodeId]: res.data.mappings,
                },
            }))
        } catch (e) {
            console.error('Failed to load mappings for node', nodeId, e)
        }
    },

    loadMappingsForDimension: async (projectId, dimId) => {
        set((state) => ({
            isLoadingDimMappings: { ...state.isLoadingDimMappings, [dimId]: true },
        }))
        try {
            const res = await dimensionsAPI.listMappings(projectId, dimId)
            set((state) => ({
                dimMappings: { ...state.dimMappings, [dimId]: res.data },
            }))
        } catch (e) {
            console.error('Failed to load mappings for dimension', dimId, e)
        } finally {
            set((state) => ({
                isLoadingDimMappings: { ...state.isLoadingDimMappings, [dimId]: false },
            }))
        }
    },

    deleteDimensionMapping: async (projectId, mappingId, dimId) => {
        // Optimistic update
        set((state) => ({
            dimMappings: {
                ...state.dimMappings,
                [dimId]: (state.dimMappings[dimId] ?? []).filter((m) => m.id !== mappingId),
            },
        }))
        try {
            await dimensionsAPI.deleteMapping(projectId, mappingId)
        } catch (e) {
            console.error('Failed to delete mapping', mappingId, e)
            notify.error('Не удалось удалить ассоциацию')
            // Reload to restore consistent state
            await get().loadMappingsForDimension(projectId, dimId)
        }
    },

    createDimensionMapping: async (projectId, dimId, data) => {
        try {
            const res = await dimensionsAPI.createMapping(projectId, dimId, {
                dimension_id: dimId,
                node_id: data.node_id,
                table_name: data.table_name,
                column_name: data.column_name,
                mapping_source: 'manual',
                confidence: 1.0,
            })
            set((state) => ({
                dimMappings: {
                    ...state.dimMappings,
                    [dimId]: [...(state.dimMappings[dimId] ?? []), res.data],
                },
            }))
        } catch (e) {
            console.error('Failed to create mapping', e)
            notify.error('Не удалось добавить ассоциацию')
        }
    },

    // ── Dimension CRUD ─────────────────────────────────────────────

    deleteDimension: async (projectId, dimId) => {
        // Optimistic update
        set((state) => ({
            dimensions: state.dimensions.filter((d) => d.id !== dimId),
            dimMappings: Object.fromEntries(
                Object.entries(state.dimMappings).filter(([k]) => k !== dimId)
            ),
        }))
        try {
            await dimensionsAPI.delete(projectId, dimId)
        } catch (e) {
            console.error('Failed to delete dimension', dimId, e)
            notify.error('Не удалось удалить измерение')
            // Reload to restore consistent state
            await get().loadDimensions(projectId)
        }
    },

    createDimension: async (projectId, data) => {
        try {
            const res = await dimensionsAPI.create(projectId, data)
            set((state) => ({ dimensions: [...state.dimensions, res.data] }))
            return res.data
        } catch (e) {
            console.error('Failed to create dimension', e)
            notify.error('Не удалось создать измерение')
            return null
        }
    },

    mergeDimensions: async (projectId, sourceIds, targetId) => {
        try {
            await dimensionsAPI.merge(projectId, sourceIds, targetId)
            // Refresh dimensions and mappings after merge
            await get().loadDimensions(projectId)
            // Clear stale mapping caches for merged dims
            const cleaned: Record<string, DimensionColumnMapping[]> = {}
            for (const [k, v] of Object.entries(get().dimMappings)) {
                if (!sourceIds.includes(k)) cleaned[k] = v
            }
            set({ dimMappings: cleaned })
            // Reload target mappings to get transferred ones
            await get().loadMappingsForDimension(projectId, targetId)
            notify.success('Измерения объединены')
        } catch (e) {
            console.error('Failed to merge dimensions', e)
            notify.error('Не удалось объединить измерения')
        }
    },

    // ── UI ─────────────────────────────────────────────────────────

    setFilterBarVisible: (v) => set({ isFilterBarVisible: v }),
    setFilterPanelOpen: (v) => set({ isFilterPanelOpen: v }),
    setFilterStats: (stats) => set({ filterStats: stats }),

    // ── Пересчёт pandas-цепочки ────────────────────────────────────

    computeFiltered: async () => {
        const { context, activeFilters, initiatorContentNodeIds, isComputingFiltered } = get()
        if (!context) return
        if (isComputingFiltered) return

        set({ isComputingFiltered: true })
        try {
            const body = {
                filters: activeFilters,
                initiator_content_node_ids: initiatorContentNodeIds.length > 0 ? initiatorContentNodeIds : undefined,
            }
            const res = context.type === 'board'
                ? await filtersAPI.computeFiltered(context.id, body)
                : await filtersAPI.computeFilteredDashboard(context.id, body)
            set({
                filteredNodeData: res.data.nodes,
                initiatorFullNodeData: res.data.initiator_full_data ?? {},
            })
        } catch (e) {
            console.error('Failed to compute filtered pipeline', e)
            set({ filteredNodeData: null, initiatorFullNodeData: {} })
        } finally {
            set({ isComputingFiltered: false })
        }
    },

    // ── Sync to backend ───────────────────────────────────────────

    syncFiltersToBackend: async () => {
        if (_syncTimer) clearTimeout(_syncTimer)
        _syncTimer = setTimeout(async () => {
            const { context, activeFilters } = get()
            if (!context) return
            try {
                if (context.type === 'board') {
                    await filtersAPI.setBoardFilters(context.id, activeFilters)
                } else {
                    await filtersAPI.setDashboardFilters(context.id, activeFilters)
                }
            } catch (e) {
                console.error('Failed to sync filters to backend', e)
            }
        }, SYNC_DEBOUNCE_MS)
    },

    // ── Helpers ────────────────────────────────────────────────────

    getFiltersQueryParam: () => {
        return encodeFilters(get().activeFilters)
    },

    resolveFieldToDimension: (field, nodeId) => {
        const mappings = get().nodeMappings[nodeId]
        if (!mappings) return null
        const mapping = mappings.find((m) => m.column_name === field)
        if (!mapping) return null
        return get().dimensions.find((d) => d.name === mapping.dim_name) ?? null
    },
}))
