/**
 * DashboardItemRenderer — renders a single item on the canvas.
 * Handles click-to-select, basic drag, and resize handles.
 * Will be enhanced with react-moveable for snap guides.
 * See docs/DASHBOARD_SYSTEM.md
 */
import { useRef, useState, useCallback, useEffect, useMemo, forwardRef, useImperativeHandle } from 'react'
import { createPortal } from 'react-dom'
import {
    GripVertical, Trash2,
    Bold, Italic, Underline, AlignLeft, AlignCenter, AlignRight,
    Heading1, Heading2, Heading3, List, ListOrdered, Type,
    Upload, ImageIcon, Link2, Maximize, X,
    BringToFront, SendToBack, ArrowUp, ArrowDown,
    RotateCw,
} from 'lucide-react'
import { useLibraryStore } from '@/store/libraryStore'
import { useDashboardStore } from '@/store/dashboardStore'
import { useFilterStore } from '@/store/filterStore'
import { filesAPI } from '@/services/api'
import { getViteApiBaseUrl } from '@/config/apiBase'
import { buildWidgetApiScript, injectApiScript, unescapeWidgetHtml } from '@/components/board/widgetApiScript'
import { applyFiltersToTables } from '@/types/crossFilter'
import type { DashboardItem, ItemBreakpointLayout } from '@/types/dashboard'

interface DashboardItemRendererProps {
    item: DashboardItem
    layout: ItemBreakpointLayout
    zoom: number
    isSelected: boolean
    onSelect: (multi: boolean) => void
    onDragEnd: (x: number, y: number) => void
    onResizeEnd: (width: number, height: number) => void
    onDelete: () => void
    editorMode?: 'edit' | 'view'
    snapToGrid?: boolean
    gridSize?: number
    smartGuides?: boolean
    /** Called during live drag/resize — returns snapped {x, y} if guides are active */
    onDragMove?: (itemId: string, rect: { x: number; y: number; width: number; height: number }) => { x: number; y: number }
    /** Called when drag/resize ends to clear guide lines */
    onDragStop?: () => void
}

export function DashboardItemRenderer({
    item,
    layout,
    zoom,
    isSelected,
    onSelect,
    onDragEnd,
    onResizeEnd,
    onDelete,
    editorMode = 'edit',
    snapToGrid = false,
    gridSize = 8,
    smartGuides = false,
    onDragMove,
    onDragStop,
}: DashboardItemRendererProps) {
    const ref = useRef<HTMLDivElement>(null)
    const textEditorRef = useRef<TextEditorHandle>(null)
    const [isDragging, setIsDragging] = useState(false)
    const [isResizing, setIsResizing] = useState(false)
    const [isRotating, setIsRotating] = useState(false)
    const dragStart = useRef<{ x: number; y: number; originX: number; originY: number } | null>(null)
    const resizeStart = useRef<{ x: number; y: number; originW: number; originH: number } | null>(null)
    const resizeCaptureTarget = useRef<HTMLElement | null>(null)
    const rotateStart = useRef<{ startAngle: number; originRotation: number } | null>(null)
    const [tempPos, setTempPos] = useState<{ x: number; y: number } | null>(null)
    const [tempSize, setTempSize] = useState<{ w: number; h: number } | null>(null)
    const [tempRotation, setTempRotation] = useState<number | null>(null)
    const [toolbarPos, setToolbarPos] = useState<{ left: number; top: number } | null>(null)

    // Keep toolbar position in sync with the item element
    useEffect(() => {
        const editMode = editorMode === 'edit'
        if (!isSelected || !editMode || !ref.current) {
            setToolbarPos(null)
            return
        }
        const update = () => {
            if (ref.current) {
                const rect = ref.current.getBoundingClientRect()
                setToolbarPos({ left: rect.left, top: rect.top })
            }
        }
        update()
        // Re-measure on scroll/resize anywhere in the tree
        window.addEventListener('scroll', update, true)
        window.addEventListener('resize', update)
        return () => {
            window.removeEventListener('scroll', update, true)
            window.removeEventListener('resize', update)
        }
    }, [isSelected, editorMode, tempPos, tempSize, layout.x, layout.y])

    // Snap helper
    const snap = useCallback((val: number) => {
        if (!snapToGrid) return val
        return Math.round(val / gridSize) * gridSize
    }, [snapToGrid, gridSize])

    // Core drag logic — can be triggered from body (unselected) or toolbar (selected)
    const startDrag = useCallback((e: React.MouseEvent) => {
        dragStart.current = {
            x: e.clientX,
            y: e.clientY,
            originX: layout.x,
            originY: layout.y,
        }
        setIsDragging(true)

        const handleMouseMove = (me: MouseEvent) => {
            if (!dragStart.current) return
            const dx = (me.clientX - dragStart.current.x) / zoom
            const dy = (me.clientY - dragStart.current.y) / zoom
            let newX = snap(dragStart.current.originX + dx)
            let newY = snap(dragStart.current.originY + dy)
            // Ask canvas for guide-snapped position
            if (onDragMove) {
                const snapped = onDragMove(item.id, { x: newX, y: newY, width: layout.width, height: layout.height })
                newX = snapped.x
                newY = snapped.y
            }
            setTempPos({ x: newX, y: newY })
        }

        const handleMouseUp = (me: MouseEvent) => {
            if (dragStart.current) {
                const dx = (me.clientX - dragStart.current.x) / zoom
                const dy = (me.clientY - dragStart.current.y) / zoom
                let newX = snap(dragStart.current.originX + dx)
                let newY = snap(dragStart.current.originY + dy)
                if (onDragMove) {
                    const snapped = onDragMove(item.id, { x: newX, y: newY, width: layout.width, height: layout.height })
                    newX = snapped.x
                    newY = snapped.y
                }
                if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
                    onDragEnd(newX, newY)
                }
            }
            dragStart.current = null
            setIsDragging(false)
            setTempPos(null)
            onDragStop?.()
            document.removeEventListener('mousemove', handleMouseMove)
            document.removeEventListener('mouseup', handleMouseUp)
        }

        document.addEventListener('mousemove', handleMouseMove)
        document.addEventListener('mouseup', handleMouseUp)
    }, [layout.x, layout.y, layout.width, layout.height, zoom, onDragEnd, snap, onDragMove, onDragStop, item.id])

    // Body click: select only. Drag is exclusively via the toolbar handle.
    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        e.stopPropagation()
        onSelect(e.shiftKey || e.metaKey || e.ctrlKey)
    }, [onSelect])

    // Toolbar drag handle — only way to drag
    const handleToolbarMouseDown = useCallback((e: React.MouseEvent) => {
        e.stopPropagation()
        e.preventDefault()
        startDrag(e)
    }, [startDrag])

    // Resize handle — pointer capture чтобы при уменьшении виджета хэндл не «убегал» от курсора и события не терялись
    const handleResizePointerDown = useCallback((e: React.PointerEvent) => {
        e.stopPropagation()
        e.preventDefault()
        const target = e.currentTarget as HTMLElement
        target.setPointerCapture(e.pointerId)
        resizeCaptureTarget.current = target

        resizeStart.current = {
            x: e.clientX,
            y: e.clientY,
            originW: layout.width,
            originH: layout.height,
        }
        setIsResizing(true)

        const handleResizeMove = (pe: PointerEvent) => {
            if (!resizeStart.current) return
            const dw = (pe.clientX - resizeStart.current.x) / zoom
            const dh = (pe.clientY - resizeStart.current.y) / zoom
            const newW = snap(Math.max(50, resizeStart.current.originW + dw))
            const newH = snap(Math.max(30, resizeStart.current.originH + dh))
            if (onDragMove) {
                onDragMove(item.id, { x: layout.x, y: layout.y, width: newW, height: newH })
            }
            setTempSize({ w: newW, h: newH })
        }

        const handleResizeUp = (pe: PointerEvent) => {
            if (pe.pointerId !== e.pointerId) return
            const el = resizeCaptureTarget.current
            if (el) {
                try { el.releasePointerCapture(pe.pointerId) } catch { /* already released */ }
                resizeCaptureTarget.current = null
            }
            if (resizeStart.current) {
                const dw = (pe.clientX - resizeStart.current.x) / zoom
                const dh = (pe.clientY - resizeStart.current.y) / zoom
                onResizeEnd(
                    snap(Math.max(50, resizeStart.current.originW + dw)),
                    snap(Math.max(30, resizeStart.current.originH + dh)),
                )
            }
            resizeStart.current = null
            setIsResizing(false)
            setTempSize(null)
            onDragStop?.()
            document.removeEventListener('pointermove', handleResizeMove)
            document.removeEventListener('pointerup', handleResizeUp)
            document.removeEventListener('pointercancel', handleResizeUp)
        }

        document.addEventListener('pointermove', handleResizeMove)
        document.addEventListener('pointerup', handleResizeUp)
        document.addEventListener('pointercancel', handleResizeUp)
    }, [layout.width, layout.height, layout.x, layout.y, zoom, snap, onDragMove, onResizeEnd, onDragStop])

    // Rotation handle
    const updateItem = useDashboardStore((s) => s.updateItem)
    const handleRotateMouseDown = useCallback((e: React.MouseEvent) => {
        e.stopPropagation()
        e.preventDefault()
        if (!ref.current) return

        const rect = ref.current.getBoundingClientRect()
        const centerX = rect.left + rect.width / 2
        const centerY = rect.top + rect.height / 2
        const startAngle = Math.atan2(e.clientY - centerY, e.clientX - centerX) * (180 / Math.PI)
        const originRotation = layout.rotation || 0

        rotateStart.current = { startAngle, originRotation }
        setIsRotating(true)

        const handleRotateMove = (me: MouseEvent) => {
            if (!rotateStart.current) return
            const currentAngle = Math.atan2(me.clientY - centerY, me.clientX - centerX) * (180 / Math.PI)
            let delta = currentAngle - rotateStart.current.startAngle
            let newRotation = rotateStart.current.originRotation + delta
            // Snap to 15° increments when holding Shift
            if (me.shiftKey) {
                newRotation = Math.round(newRotation / 15) * 15
            }
            // Normalize to 0-360
            newRotation = ((newRotation % 360) + 360) % 360
            setTempRotation(newRotation)
        }

        const handleRotateUp = () => {
            if (rotateStart.current && tempRotation !== null) {
                // Persist rotation — read ref for latest value
            }
            rotateStart.current = null
            setIsRotating(false)
            document.removeEventListener('mousemove', handleRotateMove)
            document.removeEventListener('mouseup', handleRotateUp)
        }

        document.addEventListener('mousemove', handleRotateMove)
        document.addEventListener('mouseup', handleRotateUp)
    }, [layout.rotation])

    // Persist rotation on end (via effect to capture latest tempRotation)
    useEffect(() => {
        if (!isRotating && tempRotation !== null) {
            updateItem(item.id, {
                layout: { desktop: { ...layout, rotation: tempRotation } } as any
            })
            setTempRotation(null)
        }
    }, [isRotating])

    const x = tempPos?.x ?? layout.x
    const y = tempPos?.y ?? layout.y
    const width = tempSize?.w ?? layout.width
    const height = tempSize?.h ?? layout.height
    const rotation = tempRotation ?? (layout.rotation || 0)

    const itemLabel = useItemLabel(item)

    const isEditMode = editorMode === 'edit'

    return (
        <div
            ref={ref}
            className={`absolute transition-shadow
                ${isEditMode && !isSelected ? 'cursor-move' : 'cursor-default'}
                ${isEditMode && isSelected && item.item_type !== 'line' ? 'ring-2 ring-primary shadow-lg' : ''}
                ${isEditMode && !isSelected && item.item_type !== 'line' ? 'hover:ring-1 hover:ring-primary/40' : ''}
                ${isDragging || isResizing ? 'z-50' : ''}`}
            style={{
                left: x * zoom,
                top: y * zoom,
                width: width * zoom,
                height: height * zoom,
                zIndex: item.z_index + (isDragging ? 1000 : 0),
                transform: rotation ? `rotate(${rotation}deg)` : undefined,
                transformOrigin: 'center center',
            }}
            onMouseDown={isEditMode ? handleMouseDown : undefined}
            onClick={(e) => e.stopPropagation()}
        >
            {/* Floating toolbar — rendered via portal so it's always on top regardless of item z-index */}
            {isEditMode && isSelected && toolbarPos && createPortal(
                <div
                    className="fixed flex items-center gap-1.5 bg-popover/95 backdrop-blur-sm rounded-md shadow-md border border-border text-xs cursor-move select-none"
                    style={{
                        left: toolbarPos.left,
                        top: toolbarPos.top - 8,
                        transform: 'translateY(-100%)',
                        zIndex: 9999,
                    }}
                >
                    {/* Drag handle + label + delete */}
                    <div
                        className="flex items-center gap-1.5 px-2.5 py-1 flex-shrink-0"
                        onMouseDown={handleToolbarMouseDown}
                    >
                        <GripVertical className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                        <span className="font-medium truncate max-w-[200px]">
                            {itemLabel}
                        </span>
                    </div>

                    {/* Rich text formatting toolbar — only for text blocks */}
                    {item.item_type === 'text' && textEditorRef.current && (
                        <TextFormattingToolbar exec={textEditorRef.current.exec} />
                    )}

                    {/* Line style controls — only for lines */}
                    {item.item_type === 'line' && (
                        <LineStyleControls item={item} />
                    )}

                    {/* Z-order controls */}
                    <ZOrderControls itemId={item.id} zIndex={item.z_index} />

                    <button
                        className="flex-shrink-0 p-0.5 mx-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                        onClick={(e) => { e.stopPropagation(); onDelete() }}
                        title="Удалить"
                    >
                        <Trash2 className="h-3.5 w-3.5" />
                    </button>
                </div>,
                document.body
            )}

            {/* Content — bg substrate only in edit mode (not for lines) */}
            <div className={`w-full h-full overflow-hidden ${isEditMode && item.item_type !== 'line' ? 'bg-card/50' : ''}`}>
                {item.item_type === 'widget' && (
                    <WidgetContent item={item} />
                )}
                {item.item_type === 'table' && (
                    <TableContent item={item} />
                )}
                {item.item_type === 'text' && (
                    <TextContent ref={textEditorRef} item={item} isSelected={isSelected} editorMode={editorMode} />
                )}
                {item.item_type === 'image' && (
                    <ImageContent item={item} isSelected={isSelected} editorMode={editorMode} />
                )}
                {item.item_type === 'line' && (
                    <LineContent item={item} layout={{ x, y, width, height }} zoom={zoom} isSelected={isSelected} editorMode={editorMode}
                        snap={snap} onDragMove={onDragMove} onDragStop={onDragStop} />
                )}
            </div>

            {/* Transparent overlay — captures clicks above iframes when NOT selected.
                When selected, overlay is removed so widget content is interactive. */}
            {isEditMode && !isSelected && (
                <div className="absolute inset-0 z-[1]" />
            )}

            {/* Resize handle — bottom-right, edit mode only (not for lines) */}
            {isEditMode && isSelected && item.item_type !== 'line' && (
                <div
                    className="absolute bottom-0 right-0 w-3 h-3 bg-primary rounded-sm cursor-se-resize z-10 touch-none"
                    style={{ transform: 'translate(50%, 50%)' }}
                    onPointerDown={handleResizePointerDown}
                />
            )}

            {/* Rotation handle — top-right outside corner, edit mode only (not for lines) */}
            {isEditMode && isSelected && item.item_type !== 'line' && (
                <div
                    className="absolute z-10"
                    style={{ top: -24, right: -24 }}
                >
                    <div
                        className="w-6 h-6 rounded-full bg-primary/90 border-2 border-background shadow-md cursor-grab active:cursor-grabbing flex items-center justify-center hover:bg-primary transition-colors"
                        onMouseDown={handleRotateMouseDown}
                        title={`Повернуть (${Math.round(rotation)}°)`}
                    >
                        <RotateCw className="h-3 w-3 text-primary-foreground" />
                    </div>
                </div>
            )}
        </div>
    )
}

/** Resolve display label for an item */
function useItemLabel(item: DashboardItem): string {
    const widgets = useLibraryStore((s) => s.widgets)
    if (item.overrides?.name) return item.overrides.name
    if (item.item_type === 'widget' && item.source_id) {
        const w = widgets.find((w) => w.id === item.source_id)
        if (w) return w.name
    }
    switch (item.item_type) {
        case 'widget': return 'Виджет'
        case 'table': return 'Таблица'
        case 'text': return 'Текст'
        case 'image': return 'Изображение'
        case 'line': return 'Линия'
        default: return 'Элемент'
    }
}

// ── Content renderers ─────────────────────────────────

function WidgetContent({ item }: { item: DashboardItem }) {
    const iframeRef = useRef<HTMLIFrameElement>(null)
    const [refreshKey, setRefreshKey] = useState(0)
    const widgets = useLibraryStore((s) => s.widgets)

    // Look up the source ProjectWidget by item.source_id
    const widget = item.source_id ? widgets.find((w) => w.id === item.source_id) : null

    // Cross-filter integration (item.id = инициатор для стека датасетов на дашборде)
    const filteredNodeData = useFilterStore((s) => s.filteredNodeData)
    const initiatorFullNodeData = useFilterStore((s) => s.initiatorFullNodeData)
    const activeFilters = useFilterStore((s) => s.activeFilters)
    const getFiltersQueryParam = useFilterStore((s) => s.getFiltersQueryParam)
    const getDataStack = useFilterStore((s) => s.getDataStack)
    const pushToDataStack = useFilterStore((s) => s.pushToDataStack)
    const handleWidgetClick = useFilterStore((s) => s.handleWidgetClick)
    const handleToggleFilter = useFilterStore((s) => s.handleWidgetToggleFilter)
    const handleRemoveFilter = useFilterStore((s) => s.handleWidgetRemoveFilter)
    const setFilters = useFilterStore((s) => s.setFilters)

    // Listen for widget postMessages — only from THIS iframe
    useEffect(() => {
        const onMessage = (event: MessageEvent) => {
            // Only handle messages originating from our own iframe
            if (event.source !== iframeRef.current?.contentWindow) return

            const { type, payload } = event.data || {}
            if (!payload) return
            const { dimension, field, value, contentNodeId, widgetId, tables, filter } = payload
            switch (type) {
                case 'widget:pushDataStack':
                    if (widgetId && tables) pushToDataStack(widgetId, tables)
                    break
                case 'widget:setFilterExpression':
                    if (filter && typeof filter === 'object' && typeof filter.type === 'string') {
                        setFilters(filter)
                    }
                    break
                case 'widget:click':
                case 'widget:addFilter':
                    if ((dimension || field) != null && value != null && contentNodeId) {
                        handleWidgetClick(dimension || field, value, contentNodeId, item.id)
                    }
                    break
                case 'widget:removeFilter':
                    if (dimension) handleRemoveFilter(dimension)
                    break
                case 'widget:toggleFilter':
                    if (dimension != null && value != null && contentNodeId) {
                        handleToggleFilter(dimension, value, contentNodeId, item.id)
                    }
                    break
            }
        }
        window.addEventListener('message', onMessage)
        return () => window.removeEventListener('message', onMessage)
    }, [handleWidgetClick, handleToggleFilter, handleRemoveFilter, pushToDataStack, item.id, setFilters])

    // Пересоздаём iframe только при смене данных (filteredNodeData). activeFilters обновляются раньше,
    // к приходу filteredNodeData они уже в сторе — двойная перерисовка исчезает.
    useEffect(() => {
        setRefreshKey((prev) => prev + 1)
    }, [filteredNodeData])

    useEffect(() => {
        if (!iframeRef.current || !widget?.html_code) return

        const iframe = iframeRef.current

        const sourceContentNodeId = widget.source_content_node_id || widget.config?.sourceContentNodeId
        const authToken = localStorage.getItem('token') || ''

        // Use pipeline-precomputed tables from filteredNodeData when available (всегда отфильтрованные)
        const filteredEntry = sourceContentNodeId && filteredNodeData
            ? filteredNodeData[sourceContentNodeId]
            : null
        const precomputedTables = filteredEntry?.tables
        const dataStack = getDataStack(item.id)
        const fullEntry = sourceContentNodeId ? initiatorFullNodeData[sourceContentNodeId] : null
        const fullTablesForHighlight =
            dataStack.length > 0 ? dataStack[dataStack.length - 1].tables : (fullEntry?.tables ?? filteredEntry?.tables ?? [])
        const filteredTablesForHighlight =
            fullTablesForHighlight.length > 0 && activeFilters
                ? applyFiltersToTables(fullTablesForHighlight, activeFilters)
                : undefined

        const apiScript = sourceContentNodeId
            ? buildWidgetApiScript({
                contentNodeId: sourceContentNodeId,
                authToken,
                autoRefresh: false,
                refreshInterval: 5000,
                widgetId: item.id,
                precomputedTables: precomputedTables || undefined,
                dataStack: dataStack.length ? dataStack : undefined,
                activeFilters: getFiltersQueryParam() || undefined,
                filteredTablesForHighlight,
            })
            : ''

        const htmlCode = unescapeWidgetHtml(widget.html_code || '')
        const isFullHtmlDoc =
            htmlCode.trim().toLowerCase().startsWith('<!doctype') ||
            htmlCode.trim().toLowerCase().startsWith('<html')

        let fullHtml: string
        if (isFullHtmlDoc) {
            fullHtml = injectApiScript(htmlCode, apiScript)
        } else {
            fullHtml = `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    ${apiScript}
    <style>
        html { overflow: hidden; }
        body {
            margin: 0;
            padding: 8px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            overflow: hidden;
        }
        html, body { width: 100%; height: 100%; box-sizing: border-box; }
        * { box-sizing: border-box; }
        ${widget.css_code || ''}
    </style>
</head>
<body>
    ${htmlCode}
    ${widget.js_code ? `<script>${widget.js_code}<\/script>` : ''}
</body>
</html>`
        }
        iframe.srcdoc = fullHtml
    }, [widget?.html_code, widget?.css_code, widget?.js_code, widget?.source_content_node_id, widget?.config, refreshKey])

    return (
        <div className="w-full h-full">
            {widget?.html_code ? (
                <iframe
                    key={refreshKey}
                    ref={iframeRef}
                    title={widget.name}
                    className="w-full h-full border-0"
                />
            ) : (
                <div className="w-full h-full flex items-center justify-center text-muted-foreground text-xs">
                    {widget ? 'Нет содержимого' : 'Виджет не найден'}
                </div>
            )}
        </div>
    )
}

function TableContent({ item }: { item: DashboardItem }) {
    return (
        <div className="w-full h-full overflow-auto">
            <div className="w-full h-full flex items-center justify-center text-muted-foreground text-xs">
                Таблица
            </div>
        </div>
    )
}

/** Handle exposed by TextContent for formatting commands */
interface TextEditorHandle {
    exec: (cmd: string, value?: string) => void
}

/** Standalone formatting toolbar — rendered in the floating header */
function TextFormattingToolbar({ exec }: { exec: (cmd: string, value?: string) => void }) {
    const FmtBtn = ({ cmd, value, icon: Icon, title }: {
        cmd: string; value?: string; icon: any; title: string
    }) => (
        <button
            type="button"
            className="p-1 rounded hover:bg-muted text-foreground/80 hover:text-foreground transition-colors"
            onMouseDown={(e) => { e.preventDefault(); exec(cmd, value) }}
            title={title}
        >
            <Icon className="h-3.5 w-3.5" />
        </button>
    )

    return (
        <div className="flex items-center gap-0.5 px-1 py-0.5 border-l border-border flex-shrink-0">
            <FmtBtn cmd="bold" icon={Bold} title="Жирный (Ctrl+B)" />
            <FmtBtn cmd="italic" icon={Italic} title="Курсив (Ctrl+I)" />
            <FmtBtn cmd="underline" icon={Underline} title="Подчёркнутый (Ctrl+U)" />

            <div className="w-px h-4 bg-border mx-0.5" />

            <FmtBtn cmd="formatBlock" value="H1" icon={Heading1} title="Заголовок 1" />
            <FmtBtn cmd="formatBlock" value="H2" icon={Heading2} title="Заголовок 2" />
            <FmtBtn cmd="formatBlock" value="H3" icon={Heading3} title="Заголовок 3" />
            <FmtBtn cmd="formatBlock" value="P" icon={Type} title="Обычный текст" />

            <div className="w-px h-4 bg-border mx-0.5" />

            <FmtBtn cmd="justifyLeft" icon={AlignLeft} title="По левому краю" />
            <FmtBtn cmd="justifyCenter" icon={AlignCenter} title="По центру" />
            <FmtBtn cmd="justifyRight" icon={AlignRight} title="По правому краю" />

            <div className="w-px h-4 bg-border mx-0.5" />

            <FmtBtn cmd="insertUnorderedList" icon={List} title="Маркированный список" />
            <FmtBtn cmd="insertOrderedList" icon={ListOrdered} title="Нумерованный список" />

            <div className="w-px h-4 bg-border mx-0.5" />

            {/* Font size selector */}
            <select
                className="h-6 text-[11px] bg-transparent border border-border rounded px-1 cursor-pointer"
                defaultValue="3"
                onChange={(e) => { exec('fontSize', e.target.value) }}
                title="Размер шрифта"
            >
                <option value="1">Мелкий</option>
                <option value="2">Малый</option>
                <option value="3">Обычный</option>
                <option value="4">Средний</option>
                <option value="5">Большой</option>
                <option value="6">Крупный</option>
                <option value="7">Огромный</option>
            </select>

            {/* Color picker */}
            <label className="relative p-1 rounded hover:bg-muted cursor-pointer" title="Цвет текста">
                <div className="h-3.5 w-3.5 rounded-sm border border-border" style={{ background: 'currentColor' }} />
                <input
                    type="color"
                    className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                    onChange={(e) => exec('foreColor', e.target.value)}
                />
            </label>
        </div>
    )
}

/** Z-order controls — bring forward / send backward / front / back */
function ZOrderControls({ itemId, zIndex }: { itemId: string; zIndex: number }) {
    const updateItem = useDashboardStore((s) => s.updateItem)
    const items = useDashboardStore((s) => s.currentDashboard?.items || [])

    const allZ = items.map(i => i.z_index)
    const maxZ = Math.max(...allZ)
    const minZ = Math.min(...allZ)

    const bringToFront = (e: React.MouseEvent) => {
        e.stopPropagation()
        if (zIndex < maxZ) updateItem(itemId, { z_index: maxZ + 1 })
    }
    const sendToBack = (e: React.MouseEvent) => {
        e.stopPropagation()
        if (zIndex > minZ) updateItem(itemId, { z_index: minZ - 1 })
    }
    const bringForward = (e: React.MouseEvent) => {
        e.stopPropagation()
        updateItem(itemId, { z_index: zIndex + 1 })
    }
    const sendBackward = (e: React.MouseEvent) => {
        e.stopPropagation()
        if (zIndex > 0) updateItem(itemId, { z_index: zIndex - 1 })
    }

    return (
        <div className="flex items-center gap-0.5 px-1.5 border-l border-border">
            <button
                type="button"
                className="p-0.5 rounded hover:bg-muted text-foreground/80 hover:text-foreground transition-colors disabled:opacity-30 disabled:pointer-events-none"
                onClick={sendToBack}
                disabled={zIndex <= minZ}
                title="На задний план"
            >
                <SendToBack className="h-3.5 w-3.5" />
            </button>
            <button
                type="button"
                className="p-0.5 rounded hover:bg-muted text-foreground/80 hover:text-foreground transition-colors disabled:opacity-30 disabled:pointer-events-none"
                onClick={sendBackward}
                disabled={zIndex <= 0}
                title="Назад на один уровень"
            >
                <ArrowDown className="h-3.5 w-3.5" />
            </button>
            <button
                type="button"
                className="p-0.5 rounded hover:bg-muted text-foreground/80 hover:text-foreground transition-colors"
                onClick={bringForward}
                title="Вперёд на один уровень"
            >
                <ArrowUp className="h-3.5 w-3.5" />
            </button>
            <button
                type="button"
                className="p-0.5 rounded hover:bg-muted text-foreground/80 hover:text-foreground transition-colors disabled:opacity-30 disabled:pointer-events-none"
                onClick={bringToFront}
                disabled={zIndex >= maxZ}
                title="На передний план"
            >
                <BringToFront className="h-3.5 w-3.5" />
            </button>
        </div>
    )
}

function LineStyleControls({ item }: { item: DashboardItem }) {
    const content = item.content || {}
    const updateItem = useDashboardStore((s) => s.updateItem)

    const lineStyle: LineStyle = content.line_style || 'solid'
    const lineWidth: number = content.line_width || 2
    const lineColor: string = content.line_color || ''

    return (
        <div className="flex items-center gap-1 px-1.5 border-l border-border cursor-default">
            {/* Line style */}
            <select
                className="h-5 text-[11px] bg-transparent border-none outline-none cursor-pointer"
                value={lineStyle}
                onChange={(e) => updateItem(item.id, { content: { ...content, line_style: e.target.value } })}
                onMouseDown={(e) => e.stopPropagation()}
                title="Тип линии"
            >
                {LINE_STYLES.map(s => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                ))}
            </select>

            {/* Line width */}
            <select
                className="h-5 text-[11px] bg-transparent border-none outline-none cursor-pointer"
                value={lineWidth}
                onChange={(e) => updateItem(item.id, { content: { ...content, line_width: Number(e.target.value) } })}
                onMouseDown={(e) => e.stopPropagation()}
                title="Толщина линии"
            >
                {LINE_WIDTHS.map(w => (
                    <option key={w} value={w}>{w}px</option>
                ))}
            </select>

            {/* Line color */}
            <label
                className="relative h-5 w-5 rounded cursor-pointer flex items-center justify-center"
                title="Цвет линии"
                onMouseDown={(e) => e.stopPropagation()}
            >
                <div
                    className="w-3.5 h-3.5 rounded-sm border border-border"
                    style={{ background: lineColor || 'hsl(var(--border))' }}
                />
                <input
                    type="color"
                    className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                    value={lineColor || '#cccccc'}
                    onChange={(e) => updateItem(item.id, { content: { ...content, line_color: e.target.value } })}
                />
            </label>
        </div>
    )
}

const TextContent = forwardRef<TextEditorHandle, { item: DashboardItem; isSelected: boolean; editorMode?: string }>(
    function TextContent({ item, isSelected, editorMode }, fwdRef) {
        const content = item.content || {}
        const updateItem = useDashboardStore((s) => s.updateItem)
        const editorRef = useRef<HTMLDivElement>(null)
        const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
        const isEditMode = editorMode === 'edit'
        const isEditing = isEditMode && isSelected

        // Compute current HTML from content (always fresh)
        const getHtml = useCallback(() => {
            if (content.html) return content.html
            if (content.text) {
                const fontSize = content.fontSize || 16
                const fontWeight = content.fontWeight || 'normal'
                return `<p style="font-size:${fontSize}px;font-weight:${fontWeight}">${content.text}</p>`
            }
            return '<p>Текст</p>'
        }, [content.html, content.text, content.fontSize, content.fontWeight])

        // Set HTML when entering edit mode (contentEditable div mounts)
        useEffect(() => {
            if (editorRef.current && isEditing) {
                editorRef.current.innerHTML = getHtml()
            }
        }, [isEditing, getHtml])

        // Debounced save
        const saveContent = useCallback((html: string) => {
            if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
            saveTimerRef.current = setTimeout(() => {
                updateItem(item.id, { content: { ...item.content, html } })
            }, 600)
        }, [item.id, item.content, updateItem])

        const handleInput = useCallback(() => {
            if (!editorRef.current) return
            saveContent(editorRef.current.innerHTML)
        }, [saveContent])

        // Exec command helper — exposed via ref to the floating toolbar
        const exec = useCallback((cmd: string, value?: string) => {
            document.execCommand(cmd, false, value)
            editorRef.current?.focus()
        }, [])

        useImperativeHandle(fwdRef, () => ({ exec }), [exec])

        if (!isEditing) {
            // View / unselected: render HTML content statically
            return (
                <div
                    className="w-full h-full p-3 overflow-auto text-sm [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-2 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mb-2 [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:mb-1 [&_p]:mb-1 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5"
                    dangerouslySetInnerHTML={{ __html: content.html || content.text || 'Текст' }}
                />
            )
        }

        return (
            <div className="w-full h-full">
                {/* Editable area — full height, no inline toolbar */}
                <div
                    ref={editorRef}
                    contentEditable
                    suppressContentEditableWarning
                    className="w-full h-full p-3 overflow-auto outline-none text-sm [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-2 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mb-2 [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:mb-1 [&_p]:mb-1 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5"
                    onInput={handleInput}
                    onBlur={handleInput}
                    style={{ minHeight: 0 }}
                />
            </div>
        )
    })

/** Build a public image URL from file_id */
function imageUrl(fileId: string): string {
    const base = getViteApiBaseUrl()
    return `${base}/api/v1/files/image/${fileId}`
}

type ObjectFit = 'cover' | 'contain' | 'fill' | 'none'
const FIT_OPTIONS: { value: ObjectFit; label: string }[] = [
    { value: 'cover', label: 'Заполнить' },
    { value: 'contain', label: 'Вписать' },
    { value: 'fill', label: 'Растянуть' },
    { value: 'none', label: 'Оригинал' },
]

function ImageContent({ item, isSelected, editorMode }: { item: DashboardItem; isSelected: boolean; editorMode?: string }) {
    const content = item.content || {}
    const updateItem = useDashboardStore((s) => s.updateItem)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const [isUploading, setIsUploading] = useState(false)
    const [isDragOver, setIsDragOver] = useState(false)
    const [showUrlInput, setShowUrlInput] = useState(false)
    const [urlValue, setUrlValue] = useState('')

    const isEditMode = editorMode === 'edit'
    const isEditing = isEditMode && isSelected
    const hasImage = !!(content.url || content.file_id)
    const src = content.file_id ? imageUrl(content.file_id) : content.url || ''
    const objectFit: ObjectFit = content.object_fit || 'cover'

    const handleUpload = useCallback(async (file: File) => {
        if (!file.type.startsWith('image/')) return
        setIsUploading(true)
        try {
            const { data } = await filesAPI.upload(file)
            await updateItem(item.id, {
                content: {
                    ...item.content,
                    file_id: data.file_id,
                    filename: data.filename,
                    url: '', // clear external URL when uploading
                    alt: item.content?.alt || data.filename,
                },
            })
        } catch (e) {
            console.error('Image upload failed', e)
        } finally {
            setIsUploading(false)
        }
    }, [item.id, item.content, updateItem])

    const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) handleUpload(file)
        e.target.value = ''
    }, [handleUpload])

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragOver(false)
        const file = e.dataTransfer.files?.[0]
        if (file && file.type.startsWith('image/')) handleUpload(file)
    }, [handleUpload])

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragOver(true)
    }, [])

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragOver(false)
    }, [])

    const handleSetUrl = useCallback(() => {
        if (!urlValue.trim()) return
        updateItem(item.id, {
            content: {
                ...item.content,
                url: urlValue.trim(),
                file_id: '', // clear uploaded file when setting URL
                alt: item.content?.alt || '',
            },
        })
        setShowUrlInput(false)
        setUrlValue('')
    }, [urlValue, item.id, item.content, updateItem])

    const handleRemoveImage = useCallback(() => {
        updateItem(item.id, {
            content: { ...item.content, url: '', file_id: '', filename: '' },
        })
    }, [item.id, item.content, updateItem])

    const handleFitChange = useCallback((fit: ObjectFit) => {
        updateItem(item.id, {
            content: { ...item.content, object_fit: fit },
        })
    }, [item.id, item.content, updateItem])

    // Hidden file input
    const fileInput = (
        <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
        />
    )

    // --- View mode or no image in non-edit mode ---
    if (!isEditing) {
        if (hasImage) {
            if (objectFit === 'cover') {
                return (
                    <div className="w-full h-full overflow-hidden" style={{ backgroundImage: `url(${src})`, backgroundRepeat: 'repeat', backgroundSize: 'auto' }} />
                )
            }
            return (
                <div className="w-full h-full overflow-hidden">
                    {fileInput}
                    <img src={src} alt={content.alt || ''} className="w-full h-full" style={{ objectFit }} />
                </div>
            )
        }
        return (
            <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                <ImageIcon className="h-8 w-8 opacity-30" />
            </div>
        )
    }

    // --- Edit mode + selected ---
    if (hasImage) {
        const imageElement = objectFit === 'cover'
            ? <div className="w-full h-full" style={{ backgroundImage: `url(${src})`, backgroundRepeat: 'repeat', backgroundSize: 'auto' }} />
            : <img src={src} alt={content.alt || ''} className="w-full h-full" style={{ objectFit }} />

        return (
            <div className="w-full h-full overflow-hidden relative group">
                {fileInput}
                {imageElement}

                {/* Controls overlay */}
                <div className="absolute bottom-2 left-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {/* Object-fit selector */}
                    <select
                        className="h-6 text-[11px] bg-popover/90 backdrop-blur-sm border border-border rounded px-1 cursor-pointer"
                        value={objectFit}
                        onChange={(e) => handleFitChange(e.target.value as ObjectFit)}
                        title="Масштабирование"
                    >
                        {FIT_OPTIONS.map(o => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                    </select>

                    <div className="flex-1" />

                    {/* Replace */}
                    <button
                        className="p-1 rounded bg-popover/90 backdrop-blur-sm border border-border hover:bg-accent text-xs"
                        onClick={() => fileInputRef.current?.click()}
                        title="Заменить изображение"
                    >
                        <Upload className="h-3.5 w-3.5" />
                    </button>

                    {/* Remove */}
                    <button
                        className="p-1 rounded bg-popover/90 backdrop-blur-sm border border-border hover:bg-destructive/20 text-xs"
                        onClick={handleRemoveImage}
                        title="Удалить изображение"
                    >
                        <X className="h-3.5 w-3.5" />
                    </button>
                </div>
            </div>
        )
    }

    // --- No image: upload zone ---
    return (
        <div
            className={`w-full h-full flex flex-col items-center justify-center gap-3 p-4 transition-colors
                ${isDragOver ? 'bg-primary/10 ring-2 ring-primary ring-inset' : 'bg-muted/20'}
                ${isUploading ? 'opacity-60 pointer-events-none' : ''}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
        >
            {fileInput}

            {isUploading ? (
                <>
                    <div className="animate-spin rounded-full h-6 w-6 border-2 border-primary border-t-transparent" />
                    <span className="text-xs text-muted-foreground">Загрузка...</span>
                </>
            ) : showUrlInput ? (
                <div className="flex flex-col items-center gap-2 w-full max-w-[280px]">
                    <span className="text-xs text-muted-foreground">Вставьте URL изображения</span>
                    <input
                        type="url"
                        className="w-full h-7 text-xs border border-border rounded px-2 bg-background"
                        placeholder="https://example.com/image.png"
                        value={urlValue}
                        onChange={(e) => setUrlValue(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSetUrl()}
                        autoFocus
                    />
                    <div className="flex gap-1">
                        <button
                            className="h-6 px-2 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90"
                            onClick={handleSetUrl}
                        >
                            Применить
                        </button>
                        <button
                            className="h-6 px-2 text-xs border border-border rounded hover:bg-muted"
                            onClick={() => { setShowUrlInput(false); setUrlValue('') }}
                        >
                            Отмена
                        </button>
                    </div>
                </div>
            ) : (
                <>
                    <ImageIcon className="h-8 w-8 text-muted-foreground/40" />
                    <span className="text-xs text-muted-foreground">Перетащите изображение сюда</span>
                    <div className="flex gap-2">
                        <button
                            className="flex items-center gap-1 h-7 px-3 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <Upload className="h-3 w-3" />
                            Загрузить
                        </button>
                        <button
                            className="flex items-center gap-1 h-7 px-3 text-xs border border-border rounded-md hover:bg-muted"
                            onClick={() => setShowUrlInput(true)}
                        >
                            <Link2 className="h-3 w-3" />
                            URL
                        </button>
                    </div>
                </>
            )}
        </div>
    )
}

// ── Line Content ─────────────────────────────────────────────────
type LineStyle = 'solid' | 'dashed' | 'dotted'
const LINE_STYLES: { value: LineStyle; label: string }[] = [
    { value: 'solid', label: 'Сплошная' },
    { value: 'dashed', label: 'Пунктир' },
    { value: 'dotted', label: 'Точки' },
]
const LINE_WIDTHS = [1, 2, 3, 4, 6, 8]
const LINE_PADDING = 16 // px padding around endpoints so handles are accessible

/** Map LineStyle to SVG strokeDasharray */
function dashArray(style: LineStyle, width: number): string | undefined {
    if (style === 'dashed') return `${width * 4} ${width * 3}`
    if (style === 'dotted') return `${width} ${width * 2}`
    return undefined
}

function LineContent({
    item, layout, zoom, isSelected, editorMode, snap, onDragMove, onDragStop,
}: {
    item: DashboardItem
    layout: { x: number; y: number; width: number; height: number }
    zoom: number
    isSelected: boolean
    editorMode?: string
    snap: (val: number) => number
    onDragMove?: (itemId: string, rect: { x: number; y: number; width: number; height: number }) => { x: number; y: number }
    onDragStop?: () => void
}) {
    const content = item.content || {}
    const updateItem = useDashboardStore((s) => s.updateItem)

    const isEditMode = editorMode === 'edit'
    const isEditing = isEditMode && isSelected

    const lineWidth: number = content.line_width || 2
    const lineColor: string = content.line_color || ''
    const lineStyle: LineStyle = content.line_style || 'solid'

    // Endpoint coordinates (pixels relative to item top-left)
    const x1: number = content.x1 ?? LINE_PADDING
    const y1: number = content.y1 ?? (layout.height / 2)
    const x2: number = content.x2 ?? (layout.width - LINE_PADDING)
    const y2: number = content.y2 ?? (layout.height / 2)

    // Dragging endpoint state
    const [dragIdx, setDragIdx] = useState<1 | 2 | null>(null)
    const [dragPt, setDragPt] = useState<{ x: number; y: number } | null>(null)
    const dragRef = useRef<{
        idx: 1 | 2
        startMouse: { x: number; y: number }
        startPt: { x: number; y: number }
        otherPt: { x: number; y: number }
        itemPos: { x: number; y: number }
    } | null>(null)

    const handleEndpointMouseDown = useCallback((e: React.MouseEvent, idx: 1 | 2) => {
        e.stopPropagation()
        e.preventDefault()
        const pt = idx === 1 ? { x: x1, y: y1 } : { x: x2, y: y2 }
        const otherPt = idx === 1 ? { x: x2, y: y2 } : { x: x1, y: y1 }
        dragRef.current = {
            idx,
            startMouse: { x: e.clientX, y: e.clientY },
            startPt: pt,
            otherPt,
            itemPos: { x: layout.x, y: layout.y },
        }
        setDragIdx(idx)

        const handleMove = (me: MouseEvent) => {
            if (!dragRef.current) return
            const dx = (me.clientX - dragRef.current.startMouse.x) / zoom
            const dy = (me.clientY - dragRef.current.startMouse.y) / zoom

            // New point in canvas-absolute coords (snapped to grid)
            let newCanvasX = snap(dragRef.current.itemPos.x + dragRef.current.startPt.x + dx)
            let newCanvasY = snap(dragRef.current.itemPos.y + dragRef.current.startPt.y + dy)
            const otherCanvasX = dragRef.current.itemPos.x + dragRef.current.otherPt.x
            const otherCanvasY = dragRef.current.itemPos.y + dragRef.current.otherPt.y

            // Ask canvas for guide-snapped position (treat endpoint as a tiny rect)
            if (onDragMove) {
                const snapped = onDragMove(item.id, { x: newCanvasX, y: newCanvasY, width: 0, height: 0 })
                newCanvasX = snapped.x
                newCanvasY = snapped.y
            }

            // Compute new bounding box
            const minX = Math.min(newCanvasX, otherCanvasX) - LINE_PADDING
            const minY = Math.min(newCanvasY, otherCanvasY) - LINE_PADDING
            const maxX = Math.max(newCanvasX, otherCanvasX) + LINE_PADDING
            const maxY = Math.max(newCanvasY, otherCanvasY) + LINE_PADDING

            // Show live preview (local coords within new bounding box)
            const localX = newCanvasX - minX
            const localY = newCanvasY - minY
            setDragPt({ x: localX, y: localY })
        }

        const handleUp = (me: MouseEvent) => {
            if (!dragRef.current) return
            const dx = (me.clientX - dragRef.current.startMouse.x) / zoom
            const dy = (me.clientY - dragRef.current.startMouse.y) / zoom

            let newCanvasX = snap(dragRef.current.itemPos.x + dragRef.current.startPt.x + dx)
            let newCanvasY = snap(dragRef.current.itemPos.y + dragRef.current.startPt.y + dy)
            const otherCanvasX = dragRef.current.itemPos.x + dragRef.current.otherPt.x
            const otherCanvasY = dragRef.current.itemPos.y + dragRef.current.otherPt.y

            // Final guide snap
            if (onDragMove) {
                const snapped = onDragMove(item.id, { x: newCanvasX, y: newCanvasY, width: 0, height: 0 })
                newCanvasX = snapped.x
                newCanvasY = snapped.y
            }

            const minX = Math.min(newCanvasX, otherCanvasX) - LINE_PADDING
            const minY = Math.min(newCanvasY, otherCanvasY) - LINE_PADDING
            const maxX = Math.max(newCanvasX, otherCanvasX) + LINE_PADDING
            const maxY = Math.max(newCanvasY, otherCanvasY) + LINE_PADDING

            const newWidth = maxX - minX
            const newHeight = Math.max(maxY - minY, 4) // min 4px height

            // Endpoint local coords in new bounding box
            const movedLocal = { x: newCanvasX - minX, y: newCanvasY - minY }
            const otherLocal = { x: otherCanvasX - minX, y: otherCanvasY - minY }

            const isFirst = dragRef.current.idx === 1
            const newContent = {
                ...content,
                x1: isFirst ? movedLocal.x : otherLocal.x,
                y1: isFirst ? movedLocal.y : otherLocal.y,
                x2: isFirst ? otherLocal.x : movedLocal.x,
                y2: isFirst ? otherLocal.y : movedLocal.y,
            }

            updateItem(item.id, {
                content: newContent,
                layout: {
                    desktop: {
                        x: minX, y: minY,
                        width: newWidth, height: newHeight,
                        visible: true,
                    },
                } as any,
            })

            dragRef.current = null
            setDragIdx(null)
            setDragPt(null)
            onDragStop?.()
            document.removeEventListener('mousemove', handleMove)
            document.removeEventListener('mouseup', handleUp)
        }

        document.addEventListener('mousemove', handleMove)
        document.addEventListener('mouseup', handleUp)
    }, [x1, y1, x2, y2, layout.x, layout.y, layout.width, layout.height, zoom, content, item.id, updateItem])

    // Compute display points (during drag, live preview for dragged point)
    let dx1 = x1, dy1 = y1, dx2 = x2, dy2 = y2
    if (dragIdx && dragPt) {
        if (dragIdx === 1) { dx1 = dragPt.x; dy1 = dragPt.y }
        else { dx2 = dragPt.x; dy2 = dragPt.y }
    }

    const strokeColor = lineColor || 'hsl(var(--border))'
    const HANDLE_R = 6

    return (
        <div className="w-full h-full relative group">
            <svg
                width="100%"
                height="100%"
                className="absolute inset-0"
                style={{ overflow: 'visible' }}
            >
                <line
                    x1={dx1} y1={dy1} x2={dx2} y2={dy2}
                    stroke={strokeColor}
                    strokeWidth={lineWidth}
                    strokeDasharray={dashArray(lineStyle, lineWidth)}
                    strokeLinecap="round"
                />
            </svg>

            {/* Draggable endpoint handles — edit mode + selected */}
            {isEditing && (
                <>
                    <svg
                        className="absolute inset-0 z-10"
                        width="100%" height="100%"
                        style={{ overflow: 'visible' }}
                    >
                        {/* Endpoint 1 */}
                        <circle
                            cx={dx1} cy={dy1} r={HANDLE_R}
                            className="fill-primary stroke-background cursor-grab active:cursor-grabbing"
                            strokeWidth={2}
                            onMouseDown={(e) => handleEndpointMouseDown(e, 1)}
                        />
                        {/* Endpoint 2 */}
                        <circle
                            cx={dx2} cy={dy2} r={HANDLE_R}
                            className="fill-primary stroke-background cursor-grab active:cursor-grabbing"
                            strokeWidth={2}
                            onMouseDown={(e) => handleEndpointMouseDown(e, 2)}
                        />
                    </svg>
                </>
            )}
        </div>
    )
}