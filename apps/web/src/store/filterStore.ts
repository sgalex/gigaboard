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
    DimensionColumnMappingCreate,
    DimensionCreate,
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
    /** Кэш маппингов по dimension id (ProjectExplorer — лениво при раскрытии измерения). */
    dimMappings: Record<string, DimensionColumnMapping[]>
    isLoadingDimMappings: Record<string, boolean>

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

    // Пересчитанные данные нод (не сохраняются в БД, только для отображения)
    filteredNodeData: Record<string, FilteredNodeEntry> | null
    isComputingFiltered: boolean

    initiatorContentNodeIds: string[]
    initiatorFullNodeData: Record<string, FilteredNodeEntry>
    widgetDataStacks: Record<string, { tables: any[] }[]>
}

interface FilterActions {
    // Context
    setContext: (ctx: FilterContext) => void

    // Filter mutations
    setFilters: (filters: FilterExpression | null) => void
    addCondition: (condition: FilterCondition) => void
    removeCondition: (dimName: string) => void
    clearFilters: () => void

    // Click-to-filter from widget
    handleWidgetClick: (
        field: string,
        value: any,
        contentNodeId: string,
        initiatorWidgetId?: string
    ) => void
    handleWidgetToggleFilter: (
        dimension: string,
        value: any,
        contentNodeId: string,
        widgetId?: string
    ) => void
    handleWidgetRemoveFilter: (dimension: string) => void

    /** Условия фильтра, добавленные указанным виджетом (мини-фильтр на карточке). */
    getConditionsByInitiator: (widgetNodeId: string) => FilterCondition[]

    setInitiatorContentNodeIds: (ids: string[]) => void

    getDataStack: (widgetNodeId: string) => { tables: any[] }[]
    pushToDataStack: (widgetNodeId: string, tables: any[]) => void

    /** Резолв имени измерения по полю и content node (4-tier, см. CROSS_FILTER_SYSTEM). */
    resolveDimensionForWidget: (field: string, contentNodeId: string) => string

    // Presets
    loadPresets: (projectId: string) => Promise<void>
    applyPreset: (presetId: string) => void
    saveAsPreset: (name: string, description?: string) => Promise<void>

    // Dimensions
    loadDimensions: (projectId: string) => Promise<void>
    loadMappingsForNode: (nodeId: string) => Promise<void>
    loadMappingsForDimension: (projectId: string, dimId: string) => Promise<void>
    createDimension: (projectId: string, data: DimensionCreate) => Promise<void>
    deleteDimension: (projectId: string, dimId: string) => Promise<void>
    mergeDimensions: (projectId: string, sourceIds: string[], targetId: string) => Promise<void>
    createDimensionMapping: (
        projectId: string,
        dimId: string,
        data: Omit<DimensionColumnMappingCreate, 'dimension_id'>
    ) => Promise<void>
    deleteDimensionMapping: (projectId: string, mappingId: string, dimId: string) => Promise<void>

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
    isComputingFiltered: false,
    initiatorContentNodeIds: [],
    initiatorFullNodeData: {},
    widgetDataStacks: {},

    // ── Context ────────────────────────────────────────────────────

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
                initiatorContentNodeIds: [],
                initiatorFullNodeData: {},
                widgetDataStacks: {},
                dimMappings: {},
                isLoadingDimMappings: {},
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

    addCondition: (condition) => {
        const { activeFilters } = get()
        const existing = flattenConditions(activeFilters)
        const filtered = existing.filter((c) => {
            if (c.dim !== condition.dim) return true
            const a = condition.initiatorWidgetId
            const b = c.initiatorWidgetId
            const sameInitiator =
                (a == null && b == null) || (a != null && b != null && a === b)
            return !sameInitiator
        })
        filtered.push(condition)
        const newFilters = buildAndGroup(filtered)
        set({ activeFilters: newFilters, activePresetId: null })
        get().syncFiltersToBackend()
        get().computeFiltered()
    },

    removeCondition: (dimName) => {
        const { activeFilters } = get()
        const existing = flattenConditions(activeFilters)
        const filtered = existing.filter((c) => c.dim !== dimName)
        const newFilters = buildAndGroup(filtered)
        set({ activeFilters: newFilters, activePresetId: null })
        get().syncFiltersToBackend()
        get().computeFiltered()
    },

    clearFilters: () => {
        set({
            activeFilters: null,
            activePresetId: null,
            filterStats: [],
            filteredNodeData: null,
            initiatorContentNodeIds: [],
            initiatorFullNodeData: {},
            widgetDataStacks: {},
        })
        get().syncFiltersToBackend()
    },

    // ── Click-to-filter ────────────────────────────────────────────

    resolveDimensionForWidget: (field, contentNodeId) => {
        const direct = get().resolveFieldToDimension(field, contentNodeId)
        if (direct) return direct.name
        for (const maps of Object.values(get().nodeMappings)) {
            const mapping = maps.find((m) => m.column_name === field)
            if (mapping) {
                const dim = get().dimensions.find((d) => d.name === mapping.dim_name)
                if (dim) return dim.name
            }
        }
        const byName = get().dimensions.find((d) => d.name === field)
        if (byName) return byName.name
        return field
    },

    handleWidgetClick: (field, value, contentNodeId, initiatorWidgetId) => {
        void get().loadMappingsForNode(contentNodeId)
        const dimName = get().resolveDimensionForWidget(field, contentNodeId)
        get().addCondition({
            type: 'condition',
            dim: dimName,
            op: '==',
            value,
            initiatorWidgetId,
            initiatorContentNodeId: contentNodeId,
        })
    },

    handleWidgetToggleFilter: (dimension, value, contentNodeId, widgetId) => {
        void get().loadMappingsForNode(contentNodeId)
        const dimName = get().resolveDimensionForWidget(dimension, contentNodeId)
        const flat = flattenConditions(get().activeFilters)
        const idx = flat.findIndex(
            (c) =>
                c.dim === dimName &&
                c.op === '==' &&
                c.value === value &&
                (widgetId != null ? c.initiatorWidgetId === widgetId : !c.initiatorWidgetId)
        )
        if (idx >= 0) {
            const rest = flat.filter((_, i) => i !== idx)
            set({ activeFilters: buildAndGroup(rest), activePresetId: null })
            get().syncFiltersToBackend()
            get().computeFiltered()
            return
        }
        get().handleWidgetClick(dimension, value, contentNodeId, widgetId)
    },

    handleWidgetRemoveFilter: (dimension: string) => {
        get().removeCondition(dimension)
    },

    getConditionsByInitiator: (widgetNodeId: string) =>
        flattenConditions(get().activeFilters).filter((c) => c.initiatorWidgetId === widgetNodeId),

    setInitiatorContentNodeIds: (ids) => {
        const fnd = get().filteredNodeData
        const nextFull: Record<string, FilteredNodeEntry> = {}
        if (fnd && ids.length) {
            for (const id of ids) {
                if (fnd[id]) nextFull[id] = fnd[id]
            }
        }
        set({ initiatorContentNodeIds: ids, initiatorFullNodeData: nextFull })
    },

    getDataStack: (widgetNodeId: string) => get().widgetDataStacks[widgetNodeId] ?? [],

    pushToDataStack: (widgetNodeId, tables) => {
        set((s) => ({
            widgetDataStacks: {
                ...s.widgetDataStacks,
                [widgetNodeId]: [...(s.widgetDataStacks[widgetNodeId] ?? []), { tables }],
            },
        }))
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
        set({ isLoadingDimensions: true, dimMappings: {}, isLoadingDimMappings: {} })
        try {
            const res = await dimensionsAPI.list(projectId)
            set({ dimensions: res.data })
        } catch (e) {
            console.error('Failed to load dimensions', e)
        } finally {
            set({ isLoadingDimensions: false })
        }
    },

    loadMappingsForDimension: async (projectId, dimId) => {
        set((s) => ({
            isLoadingDimMappings: { ...s.isLoadingDimMappings, [dimId]: true },
        }))
        try {
            const res = await dimensionsAPI.listMappings(projectId, dimId)
            set((s) => ({
                dimMappings: { ...s.dimMappings, [dimId]: res.data },
                isLoadingDimMappings: { ...s.isLoadingDimMappings, [dimId]: false },
            }))
        } catch (e) {
            console.error('Failed to load dimension mappings', dimId, e)
            set((s) => ({
                isLoadingDimMappings: { ...s.isLoadingDimMappings, [dimId]: false },
            }))
        }
    },

    createDimension: async (projectId, data) => {
        try {
            const res = await dimensionsAPI.create(projectId, data)
            set((s) => ({ dimensions: [...s.dimensions, res.data] }))
            notify.success(`Измерение «${data.display_name || data.name}» создано`)
        } catch (e) {
            console.error('Failed to create dimension', e)
            notify.error('Не удалось создать измерение')
        }
    },

    deleteDimension: async (projectId, dimId) => {
        try {
            await dimensionsAPI.delete(projectId, dimId)
            set((s) => {
                const { [dimId]: _removed, ...restMaps } = s.dimMappings
                const { [dimId]: _loading, ...restLoading } = s.isLoadingDimMappings
                return {
                    dimensions: s.dimensions.filter((d) => d.id !== dimId),
                    dimMappings: restMaps,
                    isLoadingDimMappings: restLoading,
                }
            })
            notify.success('Измерение удалено')
        } catch (e) {
            console.error('Failed to delete dimension', e)
            notify.error('Не удалось удалить измерение')
        }
    },

    mergeDimensions: async (projectId, sourceIds, targetId) => {
        try {
            const res = await dimensionsAPI.mergeDimensions(projectId, {
                source_ids: sourceIds,
                target_id: targetId,
            })
            await get().loadDimensions(projectId)
            await get().loadMappingsForDimension(projectId, targetId)
            notify.success(
                `Объединено: перенесено связей ${res.data.transferred_count}, удалено измерений ${res.data.deleted_count}`,
            )
        } catch (e) {
            console.error('Failed to merge dimensions', e)
            notify.error('Не удалось объединить измерения')
        }
    },

    createDimensionMapping: async (projectId, dimId, data) => {
        try {
            await dimensionsAPI.createMapping(projectId, dimId, {
                ...data,
                dimension_id: dimId,
            })
            await get().loadMappingsForDimension(projectId, dimId)
            notify.success('Поле связано с измерением')
        } catch (e) {
            console.error('Failed to create dimension mapping', e)
            notify.error('Не удалось добавить связь')
        }
    },

    deleteDimensionMapping: async (projectId, mappingId, dimId) => {
        try {
            await dimensionsAPI.deleteMapping(projectId, mappingId)
            set((s) => ({
                dimMappings: {
                    ...s.dimMappings,
                    [dimId]: (s.dimMappings[dimId] ?? []).filter((m) => m.id !== mappingId),
                },
            }))
        } catch (e) {
            console.error('Failed to delete dimension mapping', e)
            notify.error('Не удалось удалить связь')
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

    // ── UI ─────────────────────────────────────────────────────────

    setFilterBarVisible: (v) => set({ isFilterBarVisible: v }),
    setFilterPanelOpen: (v) => set({ isFilterPanelOpen: v }),
    setFilterStats: (stats) => set({ filterStats: stats }),

    // ── Пересчёт pandas-цепочки ────────────────────────────────────

    computeFiltered: async () => {
        const { context, activeFilters, isComputingFiltered } = get()
        if (!context || (context.type !== 'board' && context.type !== 'dashboard')) return
        if (isComputingFiltered) return

        set({ isComputingFiltered: true })
        try {
            const res =
                context.type === 'board'
                    ? await filtersAPI.computeFiltered(context.id, activeFilters)
                    : await filtersAPI.computeDashboardFiltered(context.id, activeFilters)
            const nodes = res.data.nodes as Record<string, FilteredNodeEntry>
            set({ filteredNodeData: nodes })
            const ids = get().initiatorContentNodeIds
            if (ids.length && nodes) {
                const nextFull: Record<string, FilteredNodeEntry> = {}
                for (const id of ids) {
                    if (nodes[id]) nextFull[id] = nodes[id]
                }
                set({ initiatorFullNodeData: nextFull })
            }
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
