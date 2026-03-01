/**
 * Dashboard Store — manages dashboards and canvas items
 * See docs/DASHBOARD_SYSTEM.md
 */
import { create } from 'zustand'
import { dashboardsAPI } from '@/services/api'
import { notify } from './notificationStore'
import type {
    Dashboard, DashboardCreate, DashboardUpdate, DashboardWithItems,
    DashboardItem, DashboardItemCreate, DashboardItemUpdate,
    BatchItemUpdate,
    DashboardShare, DashboardShareCreate,
} from '@/types/dashboard'

const DEFAULT_CANVAS_WIDTH = 1440
const DEFAULT_CANVAS_HEIGHT = 900

function normalizeDashboardSettings<T extends { settings?: Record<string, unknown> | null }>(d: T): T {
    if (!d.settings) return d
    const s = { ...d.settings }
    if (s.canvas_width == null) s.canvas_width = DEFAULT_CANVAS_WIDTH
    if (s.canvas_height == null) s.canvas_height = DEFAULT_CANVAS_HEIGHT
    return { ...d, settings: s }
}

type Breakpoint = 'desktop' | 'tablet' | 'mobile';

interface DashboardStore {
    // State
    dashboards: Dashboard[]
    currentDashboard: DashboardWithItems | null
    selectedItemIds: string[]
    activeBreakpoint: Breakpoint
    isLoading: boolean
    isSaving: boolean
    error: string | null

    // Dashboard CRUD
    fetchDashboards: (projectId: string) => Promise<void>
    createDashboard: (data: DashboardCreate) => Promise<Dashboard | null>
    fetchDashboard: (id: string) => Promise<void>
    updateDashboard: (id: string, data: DashboardUpdate) => Promise<void>
    deleteDashboard: (id: string) => Promise<void>

    // Item CRUD
    addItem: (data: DashboardItemCreate) => Promise<DashboardItem | null>
    updateItem: (itemId: string, data: DashboardItemUpdate) => Promise<void>
    removeItem: (itemId: string) => Promise<void>
    duplicateItem: (itemId: string) => Promise<DashboardItem | null>
    batchUpdateItems: (updates: BatchItemUpdate[]) => Promise<void>

    // Selection
    selectItem: (itemId: string, multi?: boolean) => void
    deselectAll: () => void

    // Breakpoint
    setBreakpoint: (bp: Breakpoint) => void

    // Sharing
    share: DashboardShare | null
    createShare: (data: DashboardShareCreate) => Promise<DashboardShare | null>
    fetchShare: () => Promise<void>
    deleteShare: () => Promise<void>

    // Reset
    reset: () => void
}

export const useDashboardStore = create<DashboardStore>((set, get) => ({
    dashboards: [],
    currentDashboard: null,
    selectedItemIds: [],
    activeBreakpoint: 'desktop',
    isLoading: false,
    isSaving: false,
    error: null,
    share: null,

    // ── Dashboard CRUD ──────────────────────────

    fetchDashboards: async (projectId: string) => {
        try {
            set({ isLoading: true, error: null })
            const { data } = await dashboardsAPI.list(projectId)
            set({ dashboards: data.map(normalizeDashboardSettings), isLoading: false })
        } catch (err: any) {
            set({ isLoading: false, error: err.message })
        }
    },

    createDashboard: async (data: DashboardCreate) => {
        try {
            const { data: dashboard } = await dashboardsAPI.create(data)
            const normalized = normalizeDashboardSettings(dashboard)
            set({ dashboards: [normalized, ...get().dashboards] })
            notify.success('Дашборд создан')
            return normalized
        } catch (err: any) {
            notify.error('Не удалось создать дашборд')
            return null
        }
    },

    fetchDashboard: async (id: string) => {
        try {
            set({ isLoading: true, error: null })
            const { data } = await dashboardsAPI.get(id)
            set({ currentDashboard: normalizeDashboardSettings(data), isLoading: false })
        } catch (err: any) {
            set({ isLoading: false, error: err.message })
            notify.error('Не удалось загрузить дашборд')
        }
    },

    updateDashboard: async (id: string, data: DashboardUpdate) => {
        try {
            set({ isSaving: true })
            const { data: updated } = await dashboardsAPI.update(id, data)
            const normalized = normalizeDashboardSettings(updated)
            set({
                isSaving: false,
                dashboards: get().dashboards.map(d => d.id === id ? normalizeDashboardSettings({ ...d, ...normalized }) : d),
                currentDashboard: get().currentDashboard?.id === id
                    ? normalizeDashboardSettings({ ...get().currentDashboard!, ...normalized })
                    : get().currentDashboard,
            })
        } catch (err: any) {
            set({ isSaving: false })
            notify.error('Не удалось обновить дашборд')
        }
    },

    deleteDashboard: async (id: string) => {
        try {
            await dashboardsAPI.delete(id)
            set({
                dashboards: get().dashboards.filter(d => d.id !== id),
                currentDashboard: get().currentDashboard?.id === id ? null : get().currentDashboard,
            })
            notify.success('Дашборд удалён')
        } catch (err: any) {
            notify.error('Не удалось удалить дашборд')
        }
    },

    // ── Item CRUD ───────────────────────────────

    addItem: async (data: DashboardItemCreate) => {
        const dashboard = get().currentDashboard
        if (!dashboard) return null

        try {
            const { data: item } = await dashboardsAPI.addItem(dashboard.id, data)
            set({
                currentDashboard: {
                    ...dashboard,
                    items: [...dashboard.items, item],
                },
            })
            return item
        } catch (err: any) {
            notify.error('Не удалось добавить элемент')
            return null
        }
    },

    updateItem: async (itemId: string, data: DashboardItemUpdate) => {
        const dashboard = get().currentDashboard
        if (!dashboard) return

        // Optimistic local update so drag/resize don't snap back
        const optimisticItems = dashboard.items.map(i => {
            if (i.id !== itemId) return i
            const updated = { ...i }
            if (data.layout) {
                const newLayout = { ...i.layout } as any
                for (const [bp, bpLayout] of Object.entries(data.layout)) {
                    if (bpLayout) {
                        newLayout[bp] = { ...(newLayout[bp] || {}), ...bpLayout }
                    }
                }
                updated.layout = newLayout
            }
            if (data.overrides) updated.overrides = { ...i.overrides, ...data.overrides }
            if (data.content) updated.content = { ...i.content, ...data.content }
            if (data.z_index !== undefined) updated.z_index = data.z_index
            return updated
        })
        set({ currentDashboard: { ...dashboard, items: optimisticItems } })

        try {
            const { data: updated } = await dashboardsAPI.updateItem(dashboard.id, itemId, data)
            // Replace with server-confirmed data
            const current = get().currentDashboard
            if (current) {
                set({
                    currentDashboard: {
                        ...current,
                        items: current.items.map(i => i.id === itemId ? updated : i),
                    },
                })
            }
        } catch (err: any) {
            // Revert on error
            set({ currentDashboard: dashboard })
            notify.error('Не удалось обновить элемент')
        }
    },

    removeItem: async (itemId: string) => {
        const dashboard = get().currentDashboard
        if (!dashboard) return

        try {
            await dashboardsAPI.removeItem(dashboard.id, itemId)
            set({
                currentDashboard: {
                    ...dashboard,
                    items: dashboard.items.filter(i => i.id !== itemId),
                },
                selectedItemIds: get().selectedItemIds.filter(id => id !== itemId),
            })
        } catch (err: any) {
            notify.error('Не удалось удалить элемент')
        }
    },

    duplicateItem: async (itemId: string) => {
        const dashboard = get().currentDashboard
        if (!dashboard) return null

        try {
            const { data: item } = await dashboardsAPI.duplicateItem(dashboard.id, itemId)
            set({
                currentDashboard: {
                    ...dashboard,
                    items: [...dashboard.items, item],
                },
                selectedItemIds: [item.id],
            })
            return item
        } catch (err: any) {
            notify.error('Не удалось дублировать элемент')
            return null
        }
    },

    batchUpdateItems: async (updates: BatchItemUpdate[]) => {
        const dashboard = get().currentDashboard
        if (!dashboard) return

        try {
            set({ isSaving: true })
            const { data: items } = await dashboardsAPI.batchUpdateItems(dashboard.id, updates)
            set({
                isSaving: false,
                currentDashboard: {
                    ...dashboard,
                    items,
                },
            })
        } catch (err: any) {
            set({ isSaving: false })
            notify.error('Не удалось сохранить изменения')
        }
    },

    // ── Selection ───────────────────────────────

    selectItem: (itemId: string, multi = false) => {
        if (multi) {
            const ids = get().selectedItemIds
            set({
                selectedItemIds: ids.includes(itemId)
                    ? ids.filter(id => id !== itemId)
                    : [...ids, itemId],
            })
        } else {
            set({ selectedItemIds: [itemId] })
        }
    },

    deselectAll: () => set({ selectedItemIds: [] }),

    // ── Breakpoint ──────────────────────────────

    setBreakpoint: (bp: Breakpoint) => set({ activeBreakpoint: bp }),

    // ── Sharing ─────────────────────────────────

    createShare: async (data: DashboardShareCreate) => {
        const dashboard = get().currentDashboard
        if (!dashboard) return null

        try {
            const { data: share } = await dashboardsAPI.createShare(dashboard.id, data)
            set({ share })
            notify.success('Ссылка для шаринга создана')
            return share
        } catch (err: any) {
            notify.error('Не удалось создать ссылку')
            return null
        }
    },

    fetchShare: async () => {
        const dashboard = get().currentDashboard
        if (!dashboard) return

        try {
            const { data: share } = await dashboardsAPI.getShare(dashboard.id)
            set({ share })
        } catch {
            set({ share: null })
        }
    },

    deleteShare: async () => {
        const dashboard = get().currentDashboard
        if (!dashboard) return

        try {
            await dashboardsAPI.deleteShare(dashboard.id)
            set({ share: null })
            notify.success('Ссылка отключена')
        } catch (err: any) {
            notify.error('Не удалось удалить ссылку')
        }
    },

    // ── Reset ───────────────────────────────────

    reset: () => set({
        dashboards: [],
        currentDashboard: null,
        selectedItemIds: [],
        activeBreakpoint: 'desktop',
        isLoading: false,
        isSaving: false,
        error: null,
        share: null,
    }),
}))
