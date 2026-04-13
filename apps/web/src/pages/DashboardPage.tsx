/**
 * DashboardPage — free-form canvas editor for dashboards.
 * Rendered inside AppLayout with ProjectExplorer sidebar (same shell as BoardPage).
 * See docs/DASHBOARD_SYSTEM.md
 */
import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { useParams } from 'react-router-dom'
import {
    Monitor, Tablet, Smartphone, Plus, Share2,
    ZoomIn, ZoomOut, Grid3X3, Trash2, Copy,
    Pencil, Eye, Magnet, Ruler, ExternalLink,
    BarChart3, Table2, Gauge, Component, Image, Spline,
    Type as TypeIcon, Camera,
} from 'lucide-react'
import { domToBlob } from 'modern-screenshot'
import { filesAPI, getFileImageUrl } from '@/services/api'
import { notify } from '@/store/notificationStore'
import { Button } from '@/components/ui/button'
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
    DropdownMenuLabel,
} from '@/components/ui/dropdown-menu'
import { AppLayout } from '@/components/layout/AppLayout'
import { ProjectExplorer } from '@/components/ProjectExplorer'
import { useDashboardStore } from '@/store/dashboardStore'
import { useProjectStore } from '@/store/projectStore'
import { useLibraryStore } from '@/store/libraryStore'
import { DashboardCanvas } from '@/components/dashboard/DashboardCanvas'
import { AIAssistantPanel } from '@/components/board/AIAssistantPanel'
import { FilterBar } from '@/components/filters/FilterBar'
import { FilterPanel } from '@/components/filters/FilterPanel'
import { useFilterStore } from '@/store/filterStore'
import type { DashboardItemCreate, ProjectWidget } from '@/types/dashboard'

type Breakpoint = 'desktop' | 'tablet' | 'mobile';

const BREAKPOINT_ICONS: Record<Breakpoint, typeof Monitor> = {
    desktop: Monitor,
    tablet: Tablet,
    mobile: Smartphone,
}

/** Icon + color per widget_type stored in config */
const WIDGET_TYPE_ICONS: Record<string, { icon: React.ElementType; color: string }> = {
    chart: { icon: BarChart3, color: 'text-blue-500' },
    table: { icon: Table2, color: 'text-green-500' },
    metric: { icon: Gauge, color: 'text-amber-500' },
    text: { icon: TypeIcon, color: 'text-purple-500' },
    custom: { icon: Component, color: 'text-cyan-500' },
}

function getWidgetIcon(widget: ProjectWidget) {
    const wtype = (widget.config as Record<string, any>)?.widget_type || 'custom'
    return WIDGET_TYPE_ICONS[wtype] || WIDGET_TYPE_ICONS.custom
}

export function DashboardPage() {
    const { projectId, dashboardId } = useParams()
    const { fetchProject } = useProjectStore()
    const {
        currentDashboard, fetchDashboard, updateDashboard,
        addItem, removeItem, duplicateItem, updateItem,
        selectedItemIds, selectItem, deselectAll,
        activeBreakpoint, setBreakpoint,
        isLoading, isSaving,
    } = useDashboardStore()
    const { widgets, tables, fetchWidgets, fetchTables } = useLibraryStore()
    const {
        setContext, loadDimensions, loadPresets, applyPreset, presets,
        activeFilters, setInitiatorContentNodeIds, getConditionsByInitiator,
    } = useFilterStore()

    const [showGrid, setShowGrid] = useState(true)
    const [zoom, setZoom] = useState(1)
    const [editorMode, setEditorMode] = useState<'edit' | 'view'>('edit')
    const [snapToGrid, setSnapToGrid] = useState(true)
    const [smartGuides, setSmartGuides] = useState(true)
    const [canvasElement, setCanvasElement] = useState<HTMLDivElement | null>(null)
    const [isCapturingThumbnail, setIsCapturingThumbnail] = useState(false)
    const canvasScrollRef = useRef<HTMLDivElement>(null)
    const panRef = useRef<{ active: boolean; startX: number; startY: number; scrollLeft: number; scrollTop: number }>({ active: false, startX: 0, startY: 0, scrollLeft: 0, scrollTop: 0 })

    const setCanvasElementRef = useMemo(() => setCanvasElement, [])

    // Pan canvas with middle mouse button (cursor grabbing only while dragging)
    useEffect(() => {
        const onMouseDown = (e: MouseEvent) => {
            if (e.button !== 1) return
            const container = canvasScrollRef.current
            if (!container || !container.contains(e.target as Node)) return
            e.preventDefault()
            e.stopPropagation()
            document.body.style.cursor = 'grabbing'
            document.body.style.userSelect = 'none'
            panRef.current = {
                active: true,
                startX: e.clientX,
                startY: e.clientY,
                scrollLeft: container.scrollLeft,
                scrollTop: container.scrollTop,
            }
        }
        const onMouseMove = (e: MouseEvent) => {
            if (!panRef.current.active || !canvasScrollRef.current) return
            e.preventDefault()
            const el = canvasScrollRef.current
            const { startX, startY, scrollLeft, scrollTop } = panRef.current
            el.scrollLeft = scrollLeft + (startX - e.clientX)
            el.scrollTop = scrollTop + (startY - e.clientY)
            panRef.current.scrollLeft = el.scrollLeft
            panRef.current.scrollTop = el.scrollTop
            panRef.current.startX = e.clientX
            panRef.current.startY = e.clientY
        }
        const onMouseUp = (e: MouseEvent) => {
            if (e.button === 1) {
                panRef.current.active = false
                document.body.style.removeProperty('cursor')
                document.body.style.removeProperty('user-select')
            }
        }

        window.addEventListener('mousedown', onMouseDown, { capture: true, passive: false })
        window.addEventListener('mousemove', onMouseMove, { passive: false })
        window.addEventListener('mouseup', onMouseUp)
        return () => {
            window.removeEventListener('mousedown', onMouseDown, { capture: true })
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('mouseup', onMouseUp)
        }
    }, [])

    useEffect(() => {
        if (projectId) {
            fetchProject(projectId)
            loadDimensions(projectId)
            loadPresets(projectId)
        }
        if (dashboardId) {
            fetchDashboard(dashboardId)
        }
    }, [projectId, dashboardId, fetchProject, fetchDashboard, loadDimensions, loadPresets])

    // Set cross-filter context + auto-apply default preset
    useEffect(() => {
        if (projectId && dashboardId) {
            setContext({ type: 'dashboard', id: dashboardId, projectId })
        }
        return () => setContext(null)
    }, [projectId, dashboardId, setContext])

    // Виджеты-инициаторы (элемент дашборда) — полные данные для подсветки сегмента (как на доске)
    useEffect(() => {
        if (!dashboardId) return
        const items = currentDashboard?.items ?? []
        const ids: string[] = []
        for (const it of items) {
            if (it.item_type !== 'widget' || !it.source_id) continue
            const w = widgets.find((x) => x.id === it.source_id)
            const sourceCn =
                w?.source_content_node_id
                ?? (w?.config as Record<string, unknown> | undefined)?.sourceContentNodeId
            if (typeof sourceCn === 'string' && getConditionsByInitiator(it.id).length > 0) {
                ids.push(sourceCn)
            }
        }
        setInitiatorContentNodeIds(ids)
    }, [dashboardId, currentDashboard?.items, widgets, activeFilters, getConditionsByInitiator, setInitiatorContentNodeIds])

    // Auto-apply default preset on dashboard load
    useEffect(() => {
        if (presets.length > 0 && dashboardId) {
            const def = presets.find((p) => p.is_default && (p.target_id === dashboardId || !p.target_id))
            if (def) applyPreset(def.id)
        }
    }, [presets, dashboardId, applyPreset])

    useEffect(() => {
        if (projectId) {
            fetchWidgets(projectId)
            fetchTables(projectId)
        }
    }, [projectId, fetchWidgets, fetchTables])

    // Auto-compute position for new items so they don't stack
    const getNextItemPosition = useCallback(() => {
        const items = currentDashboard?.items ?? []
        const step = 40
        const offset = items.length * step
        return { x: 50 + (offset % 400), y: 50 + Math.floor(offset / 400) * 320 }
    }, [currentDashboard?.items])

    const handleAddWidget = async (sourceId: string) => {
        const pos = getNextItemPosition()
        const data: DashboardItemCreate = {
            item_type: 'widget',
            source_id: sourceId,
            layout: {
                desktop: { x: pos.x, y: pos.y, width: 400, height: 300, visible: true },
            },
        }
        await addItem(data)
    }

    const handleAddTable = async (sourceId: string) => {
        const pos = getNextItemPosition()
        const data: DashboardItemCreate = {
            item_type: 'table',
            source_id: sourceId,
            layout: {
                desktop: { x: pos.x, y: pos.y, width: 600, height: 400, visible: true },
            },
        }
        await addItem(data)
    }

    const handleDropOnCanvas = useCallback(async (sourceId: string, itemType: string, x: number, y: number) => {
        const data: DashboardItemCreate = {
            item_type: itemType as 'widget' | 'table',
            source_id: sourceId,
            layout: {
                desktop: {
                    x,
                    y,
                    width: itemType === 'table' ? 600 : 400,
                    height: itemType === 'table' ? 400 : 300,
                    visible: true,
                },
            },
        }
        await addItem(data)
    }, [addItem])

    const handleAddText = async () => {
        const pos = getNextItemPosition()
        const data: DashboardItemCreate = {
            item_type: 'text',
            content: { text: 'Новый текст', fontSize: 16, fontWeight: 'normal' },
            layout: {
                desktop: { x: pos.x, y: pos.y, width: 300, height: 80, visible: true },
            },
        }
        await addItem(data)
    }

    const handleAddImage = async () => {
        const pos = getNextItemPosition()
        const data: DashboardItemCreate = {
            item_type: 'image',
            content: { url: '', alt: '' },
            layout: {
                desktop: { x: pos.x, y: pos.y, width: 300, height: 200, visible: true },
            },
        }
        await addItem(data)
    }

    const handleAddLine = async () => {
        const pos = getNextItemPosition()
        const PAD = 16
        const lineW = 300
        const lineH = PAD * 2
        const data: DashboardItemCreate = {
            item_type: 'line',
            content: {
                x1: PAD, y1: PAD,
                x2: lineW - PAD, y2: PAD,
                line_width: 2, line_style: 'solid', line_color: '',
            },
            layout: {
                desktop: { x: pos.x, y: pos.y, width: lineW, height: lineH, visible: true },
            },
        }
        await addItem(data)
    }

    const handleDeleteSelected = async () => {
        for (const id of selectedItemIds) {
            await removeItem(id)
        }
    }

    // Delete selected items on Delete / Backspace
    useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            if (selectedItemIds.length === 0) return
            // Don't intercept when typing in inputs
            const tag = (e.target as HTMLElement)?.tagName
            if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return
            if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault()
                handleDeleteSelected()
            }
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [selectedItemIds, removeItem])

    const handleDuplicateSelected = async () => {
        for (const id of selectedItemIds) {
            await duplicateItem(id)
        }
    }

    /** Capture canvas as image, upload, set as dashboard thumbnail (splash screen on project page). */
    const handleCaptureThumbnail = useCallback(async (silent = false) => {
        if (!canvasElement || !currentDashboard?.id) {
            if (!silent) notify.error('Канвас ещё не готов. Подождите загрузки.', { title: 'Превью' })
            return
        }
        setIsCapturingThumbnail(true)
        try {
            const scale = Math.min(2, 800 / (canvasElement.offsetWidth || 1))
            const blob = await domToBlob(canvasElement, {
                scale,
                type: 'image/png',
                quality: 0.85,
                backgroundColor: currentDashboard.settings?.background_color ?? '#ffffff',
            })
            if (!blob) throw new Error('Не удалось создать изображение')
            const file = new File([blob], `dashboard-${currentDashboard.id}.png`, { type: 'image/png' })
            const { data } = await filesAPI.upload(file)
            const thumbnailUrl = getFileImageUrl(data.file_id)
            await updateDashboard(currentDashboard.id, { thumbnail_url: thumbnailUrl })
            if (!silent) notify.success('Превью обновлено. Оно отобразится на карточке дашборда.', { title: 'Превью' })
        } catch (e) {
            console.error('Thumbnail capture failed:', e)
            if (!silent) {
                const msg = e instanceof Error ? e.message : 'Не удалось создать превью'
                notify.error(msg, { title: 'Ошибка превью' })
            }
        } finally {
            setIsCapturingThumbnail(false)
        }
    }, [canvasElement, currentDashboard, updateDashboard])

    if (isLoading || !currentDashboard) {
        return (
            <AppLayout
                sidebar={<ProjectExplorer context="dashboard" />}
                rightPanel={dashboardId ? <AIAssistantPanel contextId={dashboardId} scope="dashboard" /> : undefined}
            >
                <div className="h-full flex items-center justify-center">
                    <p className="text-muted-foreground">Загрузка дашборда...</p>
                </div>
            </AppLayout>
        )
    }

    const topbarTarget = document.getElementById('topbar-context')

    return (
        <AppLayout
            sidebar={<ProjectExplorer context="dashboard" />}
            rightPanel={dashboardId ? <AIAssistantPanel contextId={dashboardId} scope="dashboard" /> : undefined}
        >
            {/* Dashboard toolbar rendered into TopBar via portal */}
            {topbarTarget && createPortal(
                <>
                    {/* Title */}
                    <span className="font-medium text-sm truncate max-w-[200px]">
                        {currentDashboard.name}
                    </span>

                    <div className="w-px h-6 bg-border mx-1" />

                    {/* Breakpoint switcher */}
                    <div className="flex items-center gap-0.5 bg-muted rounded-md p-0.5">
                        {(['desktop', 'tablet', 'mobile'] as Breakpoint[]).map((bp) => {
                            const Icon = BREAKPOINT_ICONS[bp]
                            return (
                                <Button
                                    key={bp}
                                    variant={activeBreakpoint === bp ? 'default' : 'ghost'}
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={() => setBreakpoint(bp)}
                                >
                                    <Icon className="h-3.5 w-3.5" />
                                </Button>
                            )
                        })}
                    </div>

                    <div className="w-px h-6 bg-border mx-1" />

                    {/* Editor mode toggle */}
                    <TooltipProvider delayDuration={400}>
                        <div className="flex items-center gap-0.5 bg-muted rounded-md p-0.5">
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        variant={editorMode === 'edit' ? 'default' : 'ghost'}
                                        size="icon"
                                        className="h-7 w-7"
                                        aria-label="Редактор"
                                        onClick={() => { setEditorMode('edit'); setShowGrid(true) }}
                                    >
                                        <Pencil className="h-3.5 w-3.5" />
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom">
                                    <p className="font-medium">Редактор</p>
                                    <p className="text-xs text-muted-foreground mt-1 leading-snug">
                                        Перемещение и настройка элементов дашборда; отображается сетка для выравнивания.
                                    </p>
                                </TooltipContent>
                            </Tooltip>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        variant={editorMode === 'view' ? 'default' : 'ghost'}
                                        size="icon"
                                        className="h-7 w-7"
                                        aria-label="Просмотр"
                                        onClick={() => {
                                            setEditorMode('view')
                                            deselectAll()
                                            setTimeout(() => handleCaptureThumbnail(true), 150)
                                        }}
                                    >
                                        <Eye className="h-3.5 w-3.5" />
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom">
                                    <p className="font-medium">Просмотр</p>
                                    <p className="text-xs text-muted-foreground mt-1 leading-snug">
                                        Вид без режима редактирования, как у зрителя; при переключении обновляется миниатюра дашборда.
                                    </p>
                                </TooltipContent>
                            </Tooltip>
                        </div>
                    </TooltipProvider>

                    {/* Open in a new window (view mode with shareable URL) */}
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        title="Открыть в отдельном окне"
                        onClick={() => {
                            const viewUrl = `/project/${projectId}/dashboard/${dashboardId}/view`
                            setEditorMode('view')
                            deselectAll()
                            setTimeout(() => {
                                handleCaptureThumbnail(true)
                                window.open(viewUrl, '_blank')
                            }, 150)
                        }}
                    >
                        <ExternalLink className="h-3.5 w-3.5" />
                    </Button>

                    <div className="w-px h-6 bg-border mx-1" />

                    {/* Add Elements — only in edit mode */}
                    {editorMode === 'edit' && (
                        <>
                            {/* Quick-add element buttons */}
                            <Button variant="ghost" size="icon" className="h-7 w-7" title="Текстовый блок" onClick={handleAddText}>
                                <TypeIcon className="h-3.5 w-3.5 text-purple-500" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7" title="Изображение" onClick={handleAddImage}>
                                <Image className="h-3.5 w-3.5 text-pink-500" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7" title="Линия" onClick={handleAddLine}>
                                <Spline className="h-3.5 w-3.5" />
                            </Button>

                            <div className="w-px h-6 bg-border mx-0.5" />

                            {/* Add widgets/tables from library */}
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="outline" size="sm" className="h-8 gap-1">
                                        <Plus className="h-3.5 w-3.5" />
                                        Виджеты
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="start" className="w-64">
                                    {widgets.length > 0 && (
                                        <>
                                            <DropdownMenuLabel className="text-xs text-muted-foreground">Виджеты</DropdownMenuLabel>
                                            {widgets.map(w => {
                                                const { icon: WIcon, color } = getWidgetIcon(w)
                                                return (
                                                    <DropdownMenuItem key={w.id} onClick={() => handleAddWidget(w.id)} className="gap-2">
                                                        <WIcon className={`h-4 w-4 flex-shrink-0 ${color}`} />
                                                        <div className="flex flex-col min-w-0">
                                                            <span className="truncate">{w.name}</span>
                                                            {w.description && (
                                                                <span className="text-[10px] text-muted-foreground truncate">{w.description}</span>
                                                            )}
                                                        </div>
                                                    </DropdownMenuItem>
                                                )
                                            })}
                                        </>
                                    )}

                                    {tables.length > 0 && (
                                        <>
                                            {widgets.length > 0 && <DropdownMenuSeparator />}
                                            <DropdownMenuLabel className="text-xs text-muted-foreground">Таблицы</DropdownMenuLabel>
                                            {tables.map(t => (
                                                <DropdownMenuItem key={t.id} onClick={() => handleAddTable(t.id)} className="gap-2">
                                                    <Table2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                                                    <div className="flex flex-col min-w-0">
                                                        <span className="truncate">{t.name}</span>
                                                        <span className="text-[10px] text-muted-foreground">
                                                            {t.row_count} строк · {t.columns?.length || 0} колонок
                                                        </span>
                                                    </div>
                                                </DropdownMenuItem>
                                            ))}
                                        </>
                                    )}

                                    {widgets.length === 0 && tables.length === 0 && (
                                        <DropdownMenuItem disabled>
                                            <span className="text-muted-foreground">Библиотека пуста</span>
                                        </DropdownMenuItem>
                                    )}
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </>
                    )}

                    {/* Actions on selected */}
                    {selectedItemIds.length > 0 && (
                        <>
                            <div className="w-px h-6 bg-border mx-1" />
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleDuplicateSelected}>
                                <Copy className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={handleDeleteSelected}>
                                <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                            <span className="text-xs text-muted-foreground">
                                Выбрано: {selectedItemIds.length}
                            </span>
                        </>
                    )}

                    <div className="flex-1" />

                    {/* Right: zoom + grid + share */}
                    <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setZoom(z => Math.max(0.25, z - 0.1))}>
                            <ZoomOut className="h-3.5 w-3.5" />
                        </Button>
                        <span className="text-xs w-10 text-center">{Math.round(zoom * 100)}%</span>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setZoom(z => Math.min(2, z + 0.1))}>
                            <ZoomIn className="h-3.5 w-3.5" />
                        </Button>

                        <Button
                            variant={showGrid ? 'default' : 'ghost'}
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setShowGrid(g => !g)}
                            title="Сетка"
                        >
                            <Grid3X3 className="h-3.5 w-3.5" />
                        </Button>

                        <Button
                            variant={snapToGrid ? 'default' : 'ghost'}
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setSnapToGrid(s => !s)}
                            title="Привязка к сетке"
                        >
                            <Magnet className="h-3.5 w-3.5" />
                        </Button>

                        <Button
                            variant={smartGuides ? 'default' : 'ghost'}
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setSmartGuides(s => !s)}
                            title="Умные направляющие"
                        >
                            <Ruler className="h-3.5 w-3.5" />
                        </Button>
                    </div>

                    <div className="w-px h-6 bg-border mx-1" />

                    {isSaving && (
                        <span className="text-xs text-muted-foreground animate-pulse">Сохранение...</span>
                    )}

                    <Button
                        variant="outline"
                        size="icon"
                        className="h-8 w-8"
                        title="Обновить превью (сплеш для карточки дашборда)"
                        onClick={handleCaptureThumbnail}
                        disabled={!canvasElement || isCapturingThumbnail}
                    >
                        <Camera className="h-3.5 w-3.5" />
                    </Button>

                    <Button variant="outline" size="icon" className="h-8 w-8" title="Поделиться">
                        <Share2 className="h-3.5 w-3.5" />
                    </Button>
                </>,
                topbarTarget,
            )}

            {/* Content: FilterBar + canvas — strict height so dashboard never causes page scroll */}
            <div className="flex flex-col h-full min-h-0 overflow-hidden">
                <div className="flex-shrink-0">
                    <FilterBar />
                </div>
                <div
                    ref={canvasScrollRef}
                    className="flex-1 min-h-0 overflow-auto bg-muted/20"
                    onClick={() => editorMode === 'edit' && deselectAll()}
                >
                    <DashboardCanvas
                        dashboard={currentDashboard}
                        zoom={zoom}
                        showGrid={editorMode === 'edit' && showGrid}
                        activeBreakpoint={activeBreakpoint}
                        onDropWidget={editorMode === 'edit' ? handleDropOnCanvas : undefined}
                        editorMode={editorMode}
                        snapToGrid={editorMode === 'edit' && snapToGrid}
                        smartGuides={editorMode === 'edit' && smartGuides}
                        setCanvasElement={setCanvasElementRef}
                    />
                </div>
            </div>

            {/* Filter Panel — cross-filter system */}
            <FilterPanel />
        </AppLayout>
    )
}
