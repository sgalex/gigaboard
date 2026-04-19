/**
 * Library Store — manages project widgets & tables in library
 * See docs/DASHBOARD_SYSTEM.md
 */
import { create } from 'zustand'
import { libraryAPI, sourceNodesAPI, contentNodesAPI } from '@/services/api'
import { useFilterStore } from './filterStore'
import { notify } from './notificationStore'
import type {
    ProjectWidget, ProjectWidgetCreate, ProjectWidgetUpdate,
    ProjectTable, ProjectTableCreate, ProjectTableUpdate,
} from '@/types/dashboard'
import type { BoardWithNodes } from '@/types'

/** Lightweight reference to a table found inside SourceNode/ContentNode */
export interface NodeTableRef {
    id: string            // composite: `{nodeId}:{tableIndex}`
    tableName: string
    nodeId: string
    nodeType: 'source_node' | 'content_node'
    nodeName: string      // SourceNode name or ContentNode first table fallback
    boardId: string
    boardName: string
    rowCount: number
    columnCount: number
    columns: string[]     // column names from table schema
}

interface LibraryStore {
    // State
    widgets: ProjectWidget[]
    tables: ProjectTable[]
    nodeTables: NodeTableRef[]
    isLoading: boolean
    error: string | null

    // Widget actions
    fetchWidgets: (projectId: string) => Promise<void>
    saveWidget: (projectId: string, data: ProjectWidgetCreate) => Promise<ProjectWidget | null>
    updateWidget: (projectId: string, widgetId: string, data: ProjectWidgetUpdate) => Promise<void>
    deleteWidget: (projectId: string, widgetId: string) => Promise<void>

    // Auto-sync from board
    syncWidgetToLibrary: (projectId: string, nodeId: string, boardId: string, data: {
        name: string; description?: string; html_code: string;
        css_code?: string | null; js_code?: string | null;
        widget_type?: string; source_content_node_id?: string;
    }) => Promise<void>
    removeWidgetByNodeId: (projectId: string, nodeId: string) => Promise<void>

    // Table actions
    fetchTables: (projectId: string) => Promise<void>
    saveTable: (projectId: string, data: ProjectTableCreate) => Promise<ProjectTable | null>
    updateTable: (projectId: string, tableId: string, data: ProjectTableUpdate) => Promise<void>
    deleteTable: (projectId: string, tableId: string) => Promise<void>

    // Node tables (auto-collected from boards)
    fetchNodeTables: (boards: BoardWithNodes[]) => Promise<void>

    // Full project tree refresh (nodeTables + tables + dimensions)
    refreshProjectTree: (projectId: string, boards: BoardWithNodes[]) => Promise<void>

    // Reset
    reset: () => void
}

// In-flight guard to prevent duplicate auto-sync requests for the same widget node
const _syncingWidgetNodes = new Set<string>()

/** API tables may expose columns as strings or `{ name, type }` objects */
function normalizeTableColumnNames(columns: unknown): string[] {
    if (!Array.isArray(columns)) return []
    const names: string[] = []
    for (const c of columns) {
        if (typeof c === 'string') {
            if (c) names.push(c)
        } else if (c && typeof c === 'object' && 'name' in c) {
            const n = (c as { name: unknown }).name
            if (typeof n === 'string' && n) names.push(n)
        }
    }
    return names
}

export const useLibraryStore = create<LibraryStore>((set, get) => ({
    widgets: [],
    tables: [],
    nodeTables: [],
    isLoading: false,
    error: null,

    // ── Widgets ─────────────────────────────────

    fetchWidgets: async (projectId: string) => {
        try {
            set({ isLoading: true, error: null })
            const { data } = await libraryAPI.listWidgets(projectId)
            set({ widgets: data, isLoading: false })
        } catch (err: any) {
            set({ isLoading: false, error: err.message })
        }
    },

    saveWidget: async (projectId: string, data: ProjectWidgetCreate) => {
        try {
            const { data: widget } = await libraryAPI.createWidget(projectId, data)
            set({ widgets: [widget, ...get().widgets] })
            notify.success('Виджет сохранён в библиотеку')
            return widget
        } catch (err: any) {
            notify.error('Не удалось сохранить виджет')
            return null
        }
    },

    updateWidget: async (projectId: string, widgetId: string, data: ProjectWidgetUpdate) => {
        try {
            const { data: updated } = await libraryAPI.updateWidget(projectId, widgetId, data)
            set({
                widgets: get().widgets.map(w => w.id === widgetId ? updated : w),
            })
        } catch (err: any) {
            notify.error('Не удалось обновить виджет')
        }
    },

    deleteWidget: async (projectId: string, widgetId: string) => {
        try {
            await libraryAPI.deleteWidget(projectId, widgetId)
            set({ widgets: get().widgets.filter(w => w.id !== widgetId) })
            notify.success('Виджет удалён из библиотеки')
        } catch (err: any) {
            notify.error('Не удалось удалить виджет')
        }
    },

    // ── Auto-sync from board ────────────────────

    syncWidgetToLibrary: async (projectId, nodeId, boardId, data) => {
        // Deduplication guard: skip if already syncing this node
        if (_syncingWidgetNodes.has(nodeId)) return
        _syncingWidgetNodes.add(nodeId)
        try {
            const existing = get().widgets.find(w => w.source_widget_node_id === nodeId)
            if (existing) {
                // Update existing library widget silently
                const { data: updated } = await libraryAPI.updateWidget(projectId, existing.id, {
                    name: data.name,
                    html_code: data.html_code,
                    css_code: data.css_code || undefined,
                    js_code: data.js_code || undefined,
                })
                set({ widgets: get().widgets.map(w => w.id === existing.id ? updated : w) })
            } else {
                // Create new library widget silently
                const { data: widget } = await libraryAPI.createWidget(projectId, {
                    name: data.name,
                    description: data.description,
                    html_code: data.html_code,
                    css_code: data.css_code || undefined,
                    js_code: data.js_code || undefined,
                    source_widget_node_id: nodeId,
                    source_board_id: boardId,
                    source_content_node_id: data.source_content_node_id,
                    config: data.widget_type ? { widget_type: data.widget_type } : undefined,
                })
                set({ widgets: [widget, ...get().widgets] })
            }
        } catch (err: any) {
            console.warn('Auto-sync widget to library failed:', err.message)
        } finally {
            _syncingWidgetNodes.delete(nodeId)
        }
    },

    removeWidgetByNodeId: async (projectId, nodeId) => {
        const widget = get().widgets.find(w => w.source_widget_node_id === nodeId)
        if (!widget) return
        set({ widgets: get().widgets.filter(w => w.id !== widget.id) })
        try {
            await libraryAPI.deleteWidget(projectId, widget.id)
        } catch {
            // 404 is expected if the library entry was already removed or never persisted
        }
    },

    // ── Tables ──────────────────────────────────

    fetchTables: async (projectId: string) => {
        try {
            set({ isLoading: true, error: null })
            const { data } = await libraryAPI.listTables(projectId)
            set({ tables: data, isLoading: false })
        } catch (err: any) {
            set({ isLoading: false, error: err.message })
        }
    },

    saveTable: async (projectId: string, data: ProjectTableCreate) => {
        try {
            const { data: table } = await libraryAPI.createTable(projectId, data)
            set({ tables: [table, ...get().tables] })
            notify.success('Таблица сохранена в библиотеку')
            return table
        } catch (err: any) {
            notify.error('Не удалось сохранить таблицу')
            return null
        }
    },

    updateTable: async (projectId: string, tableId: string, data: ProjectTableUpdate) => {
        try {
            const { data: updated } = await libraryAPI.updateTable(projectId, tableId, data)
            set({
                tables: get().tables.map(t => t.id === tableId ? updated : t),
            })
        } catch (err: any) {
            notify.error('Не удалось обновить таблицу')
        }
    },

    deleteTable: async (projectId: string, tableId: string) => {
        try {
            await libraryAPI.deleteTable(projectId, tableId)
            set({ tables: get().tables.filter(t => t.id !== tableId) })
            notify.success('Таблица удалена из библиотеки')
        } catch (err: any) {
            notify.error('Не удалось удалить таблицу')
        }
    },

    // ── Node Tables (auto-collected) ────────────

    fetchNodeTables: async (boards) => {
        try {
            const refs: NodeTableRef[] = []

            await Promise.all(boards.map(async (board) => {
                try {
                    const [srcRes, cntRes] = await Promise.all([
                        sourceNodesAPI.list(board.id),
                        contentNodesAPI.list(board.id),
                    ])

                    // SourceNode tables
                    for (const src of srcRes.data || []) {
                        const tables = src.content?.tables || []
                        tables.forEach((t: any, idx: number) => {
                            refs.push({
                                id: `${src.id}:${idx}`,
                                tableName: t.name || `Таблица ${idx + 1}`,
                                nodeId: src.id,
                                nodeType: 'source_node',
                                nodeName: (src.config?.name as string) || src.source_type,
                                boardId: board.id,
                                boardName: board.name,
                                rowCount: t.row_count || 0,
                                columnCount: t.column_count || 0,
                                columns: normalizeTableColumnNames(t.columns),
                            })
                        })
                    }

                    // ContentNode tables
                    for (const cnt of cntRes.data || []) {
                        const tables = cnt.content?.tables || []
                        tables.forEach((t: any, idx: number) => {
                            refs.push({
                                id: `${cnt.id}:${idx}`,
                                tableName: t.name || `Таблица ${idx + 1}`,
                                nodeId: cnt.id,
                                nodeType: 'content_node',
                                nodeName: t.name || `ContentNode`,
                                boardId: board.id,
                                boardName: board.name,
                                rowCount: t.row_count || 0,
                                columnCount: t.column_count || 0,
                                columns: normalizeTableColumnNames(t.columns),
                            })
                        })
                    }
                } catch {
                    // Skip boards that fail to load
                }
            }))

            // Deduplicate by composite id to avoid duplicate React keys
            const uniqueRefs = Array.from(
                new Map(refs.map(r => [r.id, r])).values()
            )
            set({ nodeTables: uniqueRefs })
        } catch (err: any) {
            console.warn('Failed to fetch node tables:', err.message)
        }
    },

    refreshProjectTree: async (projectId, boards) => {
        // Run all three refreshes in parallel for speed
        await Promise.all([
            get().fetchTables(projectId),
            get().fetchNodeTables(boards),
            useFilterStore.getState().loadDimensions(projectId),
        ])
    },

    reset: () => set({ widgets: [], tables: [], nodeTables: [], isLoading: false, error: null }),
}))
