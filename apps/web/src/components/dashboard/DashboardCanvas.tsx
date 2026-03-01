/**
 * DashboardCanvas — free-form 2D canvas with moveable items.
 * Uses react-moveable for pixel-perfect drag/resize/snap.
 * Note: react-moveable will be added via npm. For now this is a
 * basic implementation that works without it, using native drag.
 * See docs/DASHBOARD_SYSTEM.md
 */
import { useRef, useCallback, useMemo, useState } from 'react'
import { useDashboardStore } from '@/store/dashboardStore'
import { DashboardItemRenderer } from './DashboardItemRenderer'
import type { DashboardWithItems, DashboardItem } from '@/types/dashboard'

type Breakpoint = 'desktop' | 'tablet' | 'mobile';

interface DashboardCanvasProps {
    dashboard: DashboardWithItems
    zoom: number
    showGrid: boolean
    activeBreakpoint: Breakpoint
    /** Called when a widget/table is dropped from the project tree */
    onDropWidget?: (sourceId: string, itemType: string, x: number, y: number) => void
    editorMode?: 'edit' | 'view'
    snapToGrid?: boolean
    smartGuides?: boolean
    /** When true, removes sheet border/shadow/padding — canvas fills container */
    borderless?: boolean
    /** When true (view mode), canvas is sized to content and can be centered in viewport */
    centerInView?: boolean
    /** Callback with the canvas DOM element (for screenshot/thumbnail capture). */
    setCanvasElement?: (el: HTMLDivElement | null) => void
}

const BREAKPOINT_WIDTHS: Record<Breakpoint, number | null> = {
    desktop: null, // uses canvas_width from settings
    tablet: 768,
    mobile: 375,
}

export function DashboardCanvas({ dashboard, zoom, showGrid, activeBreakpoint, onDropWidget, editorMode = 'edit', snapToGrid = false, smartGuides = false, borderless = false, centerInView = false, setCanvasElement }: DashboardCanvasProps) {
    const canvasRef = useRef<HTMLDivElement>(null)

    const setRef = useCallback(
        (el: HTMLDivElement | null) => {
            (canvasRef as React.MutableRefObject<HTMLDivElement | null>).current = el
            setCanvasElement?.(el)
        },
        [setCanvasElement],
    )
    const { selectedItemIds, selectItem, deselectAll, updateItem, removeItem } = useDashboardStore()

    const canvasWidth = activeBreakpoint === 'desktop'
        ? (dashboard.settings?.canvas_width ?? 1440)
        : (BREAKPOINT_WIDTHS[activeBreakpoint] ?? 1440)

    const gridSize = dashboard.settings?.grid_size ?? 8

    // Compute effective layout for each item at the active breakpoint
    const getItemLayout = useCallback((item: DashboardItem) => {
        const layout = item.layout
        if (!layout) return { x: 0, y: 0, width: 400, height: 300, visible: true }

        // Try breakpoint-specific override first
        const bpLayout = layout[activeBreakpoint]
        if (bpLayout) return bpLayout

        // Fallback to desktop
        if (layout.desktop) return layout.desktop

        return { x: 0, y: 0, width: 400, height: 300, visible: true }
    }, [activeBreakpoint])

    // Compute max height from items
    const items = dashboard.items ?? []

    const maxY = useMemo(() => {
        let max = 600
        for (const item of items) {
            const l = getItemLayout(item)
            if (l.visible) {
                max = Math.max(max, l.y + l.height + 100)
            }
        }
        return max
    }, [items, getItemLayout])

    // Fixed canvas height at 100%: from settings or content (backward compat)
    const canvasHeight = dashboard.settings?.canvas_height ?? maxY

    // Snap value to grid (used only at drag-end for final position)
    const snapVal = useCallback((val: number) => {
        if (!snapToGrid) return val
        return Math.round(val / gridSize) * gridSize
    }, [snapToGrid, gridSize])

    // ── Smart Guide Lines ──
    type GuideLine = { axis: 'x' | 'y'; position: number; start: number; end: number }
    const [guideLines, setGuideLines] = useState<GuideLine[]>([])
    const SNAP_THRESHOLD = 6 // px distance to snap to a guide

    /** Called from item renderer during live drag/resize.
     *  Computes guide lines AND returns snapped {x, y} position. */
    const handleDragMove = useCallback((movingItemId: string, rect: { x: number; y: number; width: number; height: number }): { x: number; y: number } => {
        if (!smartGuides) {
            setGuideLines([])
            return { x: rect.x, y: rect.y }
        }

        const guides: GuideLine[] = []
        let snapDx = 0 // correction to apply to x
        let snapDy = 0 // correction to apply to y
        let snappedX = false
        let snappedY = false

        const movingEdges = {
            left: rect.x,
            right: rect.x + rect.width,
            centerX: rect.x + rect.width / 2,
            top: rect.y,
            bottom: rect.y + rect.height,
            centerY: rect.y + rect.height / 2,
        }

        for (const other of items) {
            if (other.id === movingItemId) continue
            const ol = getItemLayout(other)
            if (!ol.visible) continue

            const otherEdges = {
                left: ol.x,
                right: ol.x + ol.width,
                centerX: ol.x + ol.width / 2,
                top: ol.y,
                bottom: ol.y + ol.height,
                centerY: ol.y + ol.height / 2,
            }

            // Vertical guides (x-axis alignment)
            if (!snappedX) {
                const xPairs: [number, number][] = [
                    [movingEdges.left, otherEdges.left],
                    [movingEdges.left, otherEdges.right],
                    [movingEdges.right, otherEdges.left],
                    [movingEdges.right, otherEdges.right],
                    [movingEdges.centerX, otherEdges.centerX],
                ]
                for (const [mv, ov] of xPairs) {
                    if (Math.abs(mv - ov) < SNAP_THRESHOLD) {
                        snapDx = ov - mv
                        snappedX = true
                        break
                    }
                }
            }

            // Horizontal guides (y-axis alignment)
            if (!snappedY) {
                const yPairs: [number, number][] = [
                    [movingEdges.top, otherEdges.top],
                    [movingEdges.top, otherEdges.bottom],
                    [movingEdges.bottom, otherEdges.top],
                    [movingEdges.bottom, otherEdges.bottom],
                    [movingEdges.centerY, otherEdges.centerY],
                ]
                for (const [mv, ov] of yPairs) {
                    if (Math.abs(mv - ov) < SNAP_THRESHOLD) {
                        snapDy = ov - mv
                        snappedY = true
                        break
                    }
                }
            }
        }

        // Apply snap corrections
        const correctedX = rect.x + snapDx
        const correctedY = rect.y + snapDy
        const correctedRect = { x: correctedX, y: correctedY, width: rect.width, height: rect.height }

        // Recompute edges with corrected position for guide line rendering
        const finalEdges = {
            left: correctedRect.x,
            right: correctedRect.x + correctedRect.width,
            centerX: correctedRect.x + correctedRect.width / 2,
            top: correctedRect.y,
            bottom: correctedRect.y + correctedRect.height,
            centerY: correctedRect.y + correctedRect.height / 2,
        }

        for (const other of items) {
            if (other.id === movingItemId) continue
            const ol = getItemLayout(other)
            if (!ol.visible) continue

            const otherEdges = {
                left: ol.x,
                right: ol.x + ol.width,
                centerX: ol.x + ol.width / 2,
                top: ol.y,
                bottom: ol.y + ol.height,
                centerY: ol.y + ol.height / 2,
            }

            // Vertical guide lines (x alignment) — only for exact matches after snap
            const xMatches = [
                [finalEdges.left, otherEdges.left],
                [finalEdges.left, otherEdges.right],
                [finalEdges.right, otherEdges.left],
                [finalEdges.right, otherEdges.right],
                [finalEdges.centerX, otherEdges.centerX],
            ] as [number, number][]
            for (const [mv, ov] of xMatches) {
                if (Math.abs(mv - ov) < 1) {
                    const minY = Math.min(correctedRect.y, ol.y) - 10
                    const maxY = Math.max(correctedRect.y + correctedRect.height, ol.y + ol.height) + 10
                    guides.push({ axis: 'x', position: ov, start: minY, end: maxY })
                }
            }

            // Horizontal guide lines (y alignment)
            const yMatches = [
                [finalEdges.top, otherEdges.top],
                [finalEdges.top, otherEdges.bottom],
                [finalEdges.bottom, otherEdges.top],
                [finalEdges.bottom, otherEdges.bottom],
                [finalEdges.centerY, otherEdges.centerY],
            ] as [number, number][]
            for (const [mv, ov] of yMatches) {
                if (Math.abs(mv - ov) < 1) {
                    const minX = Math.min(correctedRect.x, ol.x) - 10
                    const maxX = Math.max(correctedRect.x + correctedRect.width, ol.x + ol.width) + 10
                    guides.push({ axis: 'y', position: ov, start: minX, end: maxX })
                }
            }
        }

        setGuideLines(guides)
        return { x: correctedX, y: correctedY }
    }, [smartGuides, items, getItemLayout])

    const handleDragStop = useCallback(() => {
        setGuideLines([])
    }, [])

    // Handle item drag end
    const handleItemDragEnd = useCallback((itemId: string, newX: number, newY: number) => {
        const x = Math.max(0, newX)
        const y = Math.max(0, newY)
        const item = items.find(i => i.id === itemId)
        const currentLayout = item ? getItemLayout(item) : { width: 400, height: 300 }
        updateItem(itemId, {
            layout: {
                [activeBreakpoint]: { ...currentLayout, x, y, visible: true },
            } as any,
        })
    }, [activeBreakpoint, updateItem, items, getItemLayout])

    // Handle item resize end
    const handleItemResizeEnd = useCallback((itemId: string, width: number, height: number) => {
        const w = Math.max(50, width)
        const h = Math.max(30, height)
        const item = items.find(i => i.id === itemId)
        const currentLayout = item ? getItemLayout(item) : { x: 0, y: 0 }
        updateItem(itemId, {
            layout: {
                [activeBreakpoint]: { ...currentLayout, width: w, height: h, visible: true },
            } as any,
        })
    }, [activeBreakpoint, updateItem, items, getItemLayout])

    const handleCanvasClick = (e: React.MouseEvent) => {
        if (e.target === canvasRef.current) {
            deselectAll()
        }
    }

    // ── External drag-and-drop from project tree ──
    const handleDragOver = useCallback((e: React.DragEvent) => {
        if (e.dataTransfer.types.includes('application/gigaboard-widget')) {
            e.preventDefault()
            e.dataTransfer.dropEffect = 'copy'
        }
    }, [])

    const handleDrop = useCallback((e: React.DragEvent) => {
        const raw = e.dataTransfer.getData('application/gigaboard-widget')
        if (!raw || !onDropWidget || !canvasRef.current) return
        e.preventDefault()

        try {
            const { id, type } = JSON.parse(raw) as { id: string; type: string; name: string }
            const rect = canvasRef.current.getBoundingClientRect()
            const x = (e.clientX - rect.left) / zoom
            const y = (e.clientY - rect.top) / zoom
            onDropWidget(id, type, snapVal(Math.max(0, x)), snapVal(Math.max(0, y)))
        } catch { /* ignore malformed data */ }
    }, [onDropWidget, zoom, snapVal])

    const rootClassName = centerInView
        ? 'inline-block'
        : borderless
            ? 'w-full h-full'
            : 'flex justify-center p-2'
    const EDIT_PADDING = 16
    const rootStyle = centerInView
        ? undefined
        : {
            minHeight: '100%' as const,
            minWidth: canvasWidth * zoom + EDIT_PADDING,
        }

    return (
        <div className={rootClassName} style={rootStyle}>
            <div
                ref={setRef}
                className={`relative bg-background ${borderless ? '' : 'border border-border shadow-sm'}`}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                style={{
                    width: canvasWidth * zoom,
                    height: canvasHeight * zoom,
                    minHeight: canvasHeight * zoom,
                    transform: `scale(1)`,
                    transformOrigin: 'top center',
                    backgroundImage: showGrid
                        ? `linear-gradient(to right, hsl(var(--border) / 0.3) 1px, transparent 1px),
                           linear-gradient(to bottom, hsl(var(--border) / 0.3) 1px, transparent 1px)`
                        : 'none',
                    backgroundSize: showGrid ? `${gridSize * zoom}px ${gridSize * zoom}px` : 'auto',
                }}
                onClick={handleCanvasClick}
            >
                {/* Render items */}
                {items
                    .sort((a, b) => a.z_index - b.z_index)
                    .map(item => {
                        const layout = getItemLayout(item)
                        if (!layout.visible) return null

                        return (
                            <DashboardItemRenderer
                                key={item.id}
                                item={item}
                                layout={layout}
                                zoom={zoom}
                                isSelected={selectedItemIds.includes(item.id)}
                                onSelect={(multi) => selectItem(item.id, multi)}
                                onDragEnd={(x, y) => handleItemDragEnd(item.id, x, y)}
                                onResizeEnd={(w, h) => handleItemResizeEnd(item.id, w, h)}
                                onDelete={() => removeItem(item.id)}
                                editorMode={editorMode}
                                snapToGrid={snapToGrid}
                                gridSize={gridSize}
                                smartGuides={smartGuides}
                                onDragMove={handleDragMove}
                                onDragStop={handleDragStop}
                            />
                        )
                    })}

                {/* Smart guide lines — magenta dashed with diamond endpoints */}
                {guideLines.map((g, i) => {
                    const DIAMOND = 3 // half-size of diamond marker in px
                    if (g.axis === 'x') {
                        const left = g.position * zoom
                        const top = g.start * zoom
                        const height = (g.end - g.start) * zoom
                        return (
                            <div key={`guide-${i}`} className="absolute pointer-events-none z-[100]" style={{ left: left - DIAMOND, top, width: DIAMOND * 2 + 1, height }}>
                                {/* Dashed vertical line */}
                                <div className="absolute" style={{
                                    left: DIAMOND,
                                    top: 0,
                                    width: 0,
                                    height: '100%',
                                    borderLeft: '1px dashed #e846e8',
                                }} />
                                {/* Top diamond */}
                                <div className="absolute" style={{
                                    left: 0, top: -DIAMOND,
                                    width: DIAMOND * 2 + 1, height: DIAMOND * 2 + 1,
                                    background: '#e846e8',
                                    transform: 'rotate(45deg)',
                                    borderRadius: 1,
                                    opacity: 0.85,
                                }} />
                                {/* Bottom diamond */}
                                <div className="absolute" style={{
                                    left: 0, bottom: -DIAMOND,
                                    width: DIAMOND * 2 + 1, height: DIAMOND * 2 + 1,
                                    background: '#e846e8',
                                    transform: 'rotate(45deg)',
                                    borderRadius: 1,
                                    opacity: 0.85,
                                }} />
                            </div>
                        )
                    } else {
                        const left = g.start * zoom
                        const top = g.position * zoom
                        const width = (g.end - g.start) * zoom
                        return (
                            <div key={`guide-${i}`} className="absolute pointer-events-none z-[100]" style={{ left, top: top - DIAMOND, width, height: DIAMOND * 2 + 1 }}>
                                {/* Dashed horizontal line */}
                                <div className="absolute" style={{
                                    left: 0,
                                    top: DIAMOND,
                                    width: '100%',
                                    height: 0,
                                    borderTop: '1px dashed #e846e8',
                                }} />
                                {/* Left diamond */}
                                <div className="absolute" style={{
                                    left: -DIAMOND, top: 0,
                                    width: DIAMOND * 2 + 1, height: DIAMOND * 2 + 1,
                                    background: '#e846e8',
                                    transform: 'rotate(45deg)',
                                    borderRadius: 1,
                                    opacity: 0.85,
                                }} />
                                {/* Right diamond */}
                                <div className="absolute" style={{
                                    right: -DIAMOND, top: 0,
                                    width: DIAMOND * 2 + 1, height: DIAMOND * 2 + 1,
                                    background: '#e846e8',
                                    transform: 'rotate(45deg)',
                                    borderRadius: 1,
                                    opacity: 0.85,
                                }} />
                            </div>
                        )
                    }
                })}
            </div>
        </div>
    )
}
