/**
 * UI Store - manages UI state (sidebar, selected items, etc.)
 */
import { create } from 'zustand'

// Local storage keys
const STORAGE_KEYS = {
    LEFT_PANEL_WIDTH: 'gigaboard-left-panel-width',
    RIGHT_PANEL_WIDTH: 'gigaboard-right-panel-width',
}

// Default panel widths
const DEFAULT_LEFT_PANEL_WIDTH = 320 // 80 * 4 (w-80)
const DEFAULT_RIGHT_PANEL_WIDTH = 384 // 96 * 4 (w-96)

// Load panel width from localStorage
function loadPanelWidth(key: string, defaultValue: number): number {
    try {
        const stored = localStorage.getItem(key)
        if (stored) {
            const width = parseInt(stored, 10)
            if (!isNaN(width) && width >= 200 && width <= 800) {
                return width
            }
        }
    } catch (e) {
        console.warn('Failed to load panel width from localStorage:', e)
    }
    return defaultValue
}

// Save panel width to localStorage
function savePanelWidth(key: string, width: number): void {
    try {
        localStorage.setItem(key, width.toString())
    } catch (e) {
        console.warn('Failed to save panel width to localStorage:', e)
    }
}

interface UIStore {
    // Layout state
    isProjectExplorerOpen: boolean
    isAIPanelOpen: boolean
    isInspectorPanelOpen: boolean

    // Panel widths
    leftPanelWidth: number
    rightPanelWidth: number

    // Canvas state
    canvasZoom: number
    canvasViewport: { x: number; y: number }

    // Dialog state
    isCreateProjectDialogOpen: boolean
    isCreateBoardDialogOpen: boolean
    createDashboardDialogOpen: boolean
    createDashboardProjectId: string | null
    contextProjectId: string | null
    contextBoardId: string | null
    canvasCenter: { x: number; y: number } | null

    // Actions
    toggleProjectExplorer: () => void
    toggleAIPanel: () => void
    toggleInspectorPanel: () => void
    setProjectExplorerOpen: (isOpen: boolean) => void
    setAIPanelOpen: (isOpen: boolean) => void
    setInspectorPanelOpen: (isOpen: boolean) => void

    setLeftPanelWidth: (width: number) => void
    setRightPanelWidth: (width: number) => void

    setCanvasZoom: (zoom: number) => void
    setCanvasViewport: (x: number, y: number) => void

    // Dialog actions
    openCreateProjectDialog: () => void
    closeCreateProjectDialog: () => void
    openCreateBoardDialog: (projectId?: string) => void
    closeCreateBoardDialog: () => void
    openCreateDashboardDialog: (projectId?: string) => void
    closeCreateDashboardDialog: () => void
}

export const useUIStore = create<UIStore>((set) => ({
    // Initial state
    isProjectExplorerOpen: true,
    isAIPanelOpen: false,
    isInspectorPanelOpen: false,

    leftPanelWidth: loadPanelWidth(STORAGE_KEYS.LEFT_PANEL_WIDTH, DEFAULT_LEFT_PANEL_WIDTH),
    rightPanelWidth: loadPanelWidth(STORAGE_KEYS.RIGHT_PANEL_WIDTH, DEFAULT_RIGHT_PANEL_WIDTH),

    canvasZoom: 1,
    canvasViewport: { x: 0, y: 0 },

    isCreateProjectDialogOpen: false,
    isCreateBoardDialogOpen: false,
    createDashboardDialogOpen: false,
    createDashboardProjectId: null,
    contextProjectId: null,
    contextBoardId: null,
    canvasCenter: null,

    // Toggle actions
    toggleProjectExplorer: () =>
        set((state) => ({ isProjectExplorerOpen: !state.isProjectExplorerOpen })),

    toggleAIPanel: () =>
        set((state) => ({ isAIPanelOpen: !state.isAIPanelOpen })),

    toggleInspectorPanel: () =>
        set((state) => ({ isInspectorPanelOpen: !state.isInspectorPanelOpen })),

    // Set actions
    setProjectExplorerOpen: (isOpen: boolean) =>
        set({ isProjectExplorerOpen: isOpen }),

    setAIPanelOpen: (isOpen: boolean) =>
        set({ isAIPanelOpen: isOpen }),

    setInspectorPanelOpen: (isOpen: boolean) =>
        set({ isInspectorPanelOpen: isOpen }),

    // Panel width actions
    setLeftPanelWidth: (width: number) => {
        savePanelWidth(STORAGE_KEYS.LEFT_PANEL_WIDTH, width)
        set({ leftPanelWidth: width })
    },

    setRightPanelWidth: (width: number) => {
        savePanelWidth(STORAGE_KEYS.RIGHT_PANEL_WIDTH, width)
        set({ rightPanelWidth: width })
    },

    // Canvas
    setCanvasZoom: (zoom: number) =>
        set({ canvasZoom: zoom }),

    setCanvasViewport: (x: number, y: number) =>
        set({ canvasViewport: { x, y } }),

    // Dialogs
    openCreateProjectDialog: () =>
        set({ isCreateProjectDialogOpen: true }),

    closeCreateProjectDialog: () =>
        set({ isCreateProjectDialogOpen: false }),

    openCreateBoardDialog: (projectId?: string) =>
        set({ isCreateBoardDialogOpen: true, contextProjectId: projectId || null }),

    closeCreateBoardDialog: () =>
        set({ isCreateBoardDialogOpen: false, contextProjectId: null }),

    openCreateDashboardDialog: (projectId?: string) =>
        set({ createDashboardDialogOpen: true, createDashboardProjectId: projectId || null }),

    closeCreateDashboardDialog: () =>
        set({ createDashboardDialogOpen: false, createDashboardProjectId: null }),

}))
