/**
 * DashboardViewPage — standalone view-only page for a dashboard.
 * Opened in a separate window/tab from the editor. URL is shareable.
 * Cross-filter context is set so filters work the same as in the editor.
 * See docs/DASHBOARD_SYSTEM.md, docs/CROSS_FILTER_SYSTEM.md
 */
import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useDashboardStore } from '@/store/dashboardStore'
import { useLibraryStore } from '@/store/libraryStore'
import { useFilterStore } from '@/store/filterStore'
import { DashboardCanvas } from '@/components/dashboard/DashboardCanvas'
import { FilterBar } from '@/components/filters/FilterBar'
import { FilterPanel } from '@/components/filters/FilterPanel'
import type { DashboardWithItems } from '@/types/dashboard'

function getCanvasHeight(dashboard: DashboardWithItems | null): number {
    if (!dashboard) return 900
    if (dashboard.settings?.canvas_height != null) return dashboard.settings.canvas_height
    const items = dashboard.items ?? []
        let maxY = 900
    for (const item of items) {
        const layout = item.layout?.desktop ?? item.layout
        if (layout?.visible !== false) {
            const bottom = (layout?.y ?? 0) + (layout?.height ?? 300) + 100
            maxY = Math.max(maxY, bottom)
        }
    }
    return maxY
}

export function DashboardViewPage() {
    const { projectId, dashboardId } = useParams()
    const {
        currentDashboard, fetchDashboard,
        activeBreakpoint,
        isLoading,
    } = useDashboardStore()
    const { fetchWidgets, fetchTables } = useLibraryStore()
    const { setContext, loadDimensions, loadPresets, applyPreset, presets } = useFilterStore()

    const containerRef = useRef<HTMLDivElement>(null)
    const [scale, setScale] = useState(0.25)
    const canvasWidth = currentDashboard?.settings?.canvas_width ?? 1440
    const canvasHeight = currentDashboard ? getCanvasHeight(currentDashboard) : 900

    useEffect(() => {
        if (projectId) {
            fetchWidgets(projectId)
            fetchTables(projectId)
            loadDimensions(projectId)
            loadPresets(projectId)
        }
        if (dashboardId) {
            fetchDashboard(dashboardId)
        }
    }, [projectId, dashboardId, fetchDashboard, fetchWidgets, fetchTables, loadDimensions, loadPresets])

    // Cross-filter context so backend applies filters to widget data
    useEffect(() => {
        if (projectId && dashboardId) {
            setContext({ type: 'dashboard', id: dashboardId, projectId })
        }
        return () => setContext(null)
    }, [projectId, dashboardId, setContext])

    // Auto-apply default preset when opening in new tab (same as DashboardPage)
    useEffect(() => {
        if (presets.length > 0 && dashboardId) {
            const def = presets.find((p) => p.is_default && (p.target_id === dashboardId || !p.target_id))
            if (def) applyPreset(def.id)
        }
    }, [presets, dashboardId, applyPreset])

    // Масштаб по размеру области под FilterBar: дашборд вписывается без прокрутки
    useEffect(() => {
        if (!currentDashboard) return
        const el = containerRef.current
        if (!el) return
        const padding = 16
        const updateScale = () => {
            const w = el.clientWidth
            const h = el.clientHeight
            if (w <= padding || h <= padding) return
            const scaleX = (w - padding) / canvasWidth
            const scaleY = (h - padding) / canvasHeight
            setScale((prev) => {
                const next = Math.min(scaleX, scaleY)
                return next > 0 ? next : prev
            })
        }
        const ro = new ResizeObserver(updateScale)
        ro.observe(el)
        updateScale()
        const t1 = requestAnimationFrame(updateScale)
        const t2 = requestAnimationFrame(updateScale)
        const t3 = setTimeout(updateScale, 100)
        return () => {
            ro.disconnect()
            cancelAnimationFrame(t1)
            cancelAnimationFrame(t2)
            clearTimeout(t3)
        }
    }, [currentDashboard?.id, canvasWidth, canvasHeight])

    // Set document title
    useEffect(() => {
        if (currentDashboard) {
            document.title = `${currentDashboard.name} — GigaBoard`
        }
        return () => { document.title = 'GigaBoard' }
    }, [currentDashboard?.name])

    if (isLoading || !currentDashboard) {
        return (
            <div className="h-screen flex items-center justify-center bg-background">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
        )
    }

    return (
        <div className="fixed inset-0 flex flex-col overflow-hidden bg-background">
            <div className="flex-shrink-0">
                <FilterBar />
            </div>
            <div
                ref={containerRef}
                className="flex-1 min-h-0 overflow-hidden flex items-center justify-center min-w-0"
            >
                <DashboardCanvas
                    dashboard={currentDashboard}
                    zoom={scale}
                    showGrid={false}
                    activeBreakpoint={activeBreakpoint}
                    editorMode="view"
                    borderless
                    centerInView
                />
            </div>
            <FilterPanel />
        </div>
    )
}
