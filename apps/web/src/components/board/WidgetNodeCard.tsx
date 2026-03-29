import { memo, useRef, useEffect, useState } from 'react'
import { Handle, Position, NodeProps, NodeResizer } from '@xyflow/react'
import { BarChart3, Code, Sparkles, RefreshCw, MoreVertical, Timer, TimerOff, Settings, Edit2, Maximize, Table2, Gauge, Type, Component, Filter, X } from 'lucide-react'
import { WidgetNode } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useNotificationStore } from '@/store/notificationStore'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { widgetNodesAPI, contentNodesAPI } from '@/services/api'
import { useBoardStore } from '@/store/boardStore'
import { useFilterStore } from '@/store/filterStore'
import { WidgetDialog } from './WidgetDialog'
import { buildWidgetApiScript, injectApiScript, unescapeWidgetHtml } from './widgetApiScript'
import { operatorLabel, applyFiltersToTables } from '@/types/crossFilter'

/** Icon per widget_type stored in config (shared with ProjectExplorer) */
const WIDGET_TYPE_ICONS: Record<string, React.ElementType> = {
    chart: BarChart3,
    table: Table2,
    metric: Gauge,
    text: Type,
    custom: Component,
}

export const WidgetNodeCard = memo(({ data, selected, width, height }: NodeProps) => {
    const node = data.widgetNode as WidgetNode
    const iframeRef = useRef<HTMLIFrameElement>(null)
    const fullscreenIframeRef = useRef<HTMLIFrameElement>(null)
    const [refreshKey, setRefreshKey] = useState(0)
    const [showIntervalDialog, setShowIntervalDialog] = useState(false)
    const [tempInterval, setTempInterval] = useState(5)
    const [showWidgetDialog, setShowWidgetDialog] = useState(false)
    const [sourceNode, setSourceNode] = useState<any>(null)
    const [isEditingName, setIsEditingName] = useState(false)
    const [tempName, setTempName] = useState('')
    const [isFullscreen, setIsFullscreen] = useState(false)

    const showToast = useNotificationStore((state) => state.show)
    const fetchWidgetNodes = useBoardStore((state) => state.fetchWidgetNodes)
    const updateWidgetNode = useBoardStore((state) => state.updateWidgetNode)

    // Cross-filter integration
    const activeFilters = useFilterStore((state) => state.activeFilters)
    const filteredNodeData = useFilterStore((state) => state.filteredNodeData)
    const initiatorFullNodeData = useFilterStore((state) => state.initiatorFullNodeData)
    const handleWidgetClick = useFilterStore((state) => state.handleWidgetClick)
    const handleToggleFilter = useFilterStore((state) => state.handleWidgetToggleFilter)
    const handleRemoveFilter = useFilterStore((state) => state.handleWidgetRemoveFilter)
    const getFiltersQueryParam = useFilterStore((state) => state.getFiltersQueryParam)
    const getDataStack = useFilterStore((state) => state.getDataStack)
    const pushToDataStack = useFilterStore((state) => state.pushToDataStack)
    const getConditionsByInitiator = useFilterStore((state) => state.getConditionsByInitiator)
    const removeCondition = useFilterStore((state) => state.removeCondition)
    const setFilters = useFilterStore((state) => state.setFilters)
    const dimensions = useFilterStore((state) => state.dimensions)

    useEffect(() => {
        if (isFullscreen) {
            setRefreshKey(prev => prev + 1)
        }
    }, [isFullscreen])

    // Пересоздаём iframe только при смене данных (filteredNodeData). activeFilters обновляются раньше,
    // к приходу filteredNodeData они уже в сторе — двойная перерисовка исчезает.
    useEffect(() => {
        setRefreshKey(prev => prev + 1)
    }, [filteredNodeData])

    // Cross-filter: listen for widget postMessages — only from THIS iframe
    useEffect(() => {
        const onMessage = (event: MessageEvent) => {
            // Only handle messages originating from our own iframe
            const ownWindow = iframeRef.current?.contentWindow
                ?? fullscreenIframeRef.current?.contentWindow
            if (event.source !== ownWindow) return

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
                        handleWidgetClick(dimension || field, value, contentNodeId, node.id)
                    }
                    break
                case 'widget:removeFilter':
                    if (dimension) handleRemoveFilter(dimension)
                    break
                case 'widget:toggleFilter':
                    if (dimension != null && value != null && contentNodeId) {
                        handleToggleFilter(dimension, value, contentNodeId, node.id)
                    }
                    break
            }
        }
        window.addEventListener('message', onMessage)
        return () => window.removeEventListener('message', onMessage)
    }, [handleWidgetClick, handleToggleFilter, handleRemoveFilter, pushToDataStack, setFilters])

    // Use React Flow dimensions (updated in real-time during resize) or fallback to node dimensions
    const nodeWidth = width ?? node.width ?? 320
    const nodeHeight = height ?? node.height ?? 240

    // Условия, инициированные этим виджетом (для мини-фильтра внизу карточки)
    const initiatorConditions = getConditionsByInitiator(node.id)

    // Check if widget was AI-generated
    const isAIGenerated = !!node.generated_by

    // Determine icon based on widget_type
    const widgetType = (node.config as Record<string, any>)?.widget_type || 'custom'
    const HeaderIcon = WIDGET_TYPE_ICONS[widgetType] || WIDGET_TYPE_ICONS.custom

    // Handle name edit
    const handleStartEditName = () => {
        setTempName(node.name)
        setIsEditingName(true)
    }

    const handleSaveName = async () => {
        if (tempName.trim() && tempName !== node.name) {
            await updateWidgetNode(node.board_id, node.id, {
                name: tempName.trim()
            })
        }
        setIsEditingName(false)
    }

    const handleCancelEditName = () => {
        setIsEditingName(false)
        setTempName('')
    }

    // Toggle auto-refresh
    const toggleAutoRefresh = async () => {
        try {
            await widgetNodesAPI.update(node.board_id, node.id, {
                auto_refresh: !node.auto_refresh
            })
            // Refresh widget nodes to get updated data
            await fetchWidgetNodes(node.board_id)
            // Force iframe recreation
            setRefreshKey(prev => prev + 1)
        } catch (error) {
            console.error('Failed to toggle auto-refresh:', error)
        }
    }

    // Update refresh interval
    const updateInterval = async () => {
        try {
            await widgetNodesAPI.update(node.board_id, node.id, {
                refresh_interval: tempInterval * 1000
            })
            setShowIntervalDialog(false)
            // Refresh widget nodes to get updated data
            await fetchWidgetNodes(node.board_id)
            // Force iframe recreation
            setRefreshKey(prev => prev + 1)
        } catch (error) {
            console.error('Failed to update interval:', error)
        }
    }

    // Open edit dialog
    const handleEdit = async () => {
        try {
            const sourceContentNodeId = node.config?.sourceContentNodeId
            if (!sourceContentNodeId) {
                console.error('No source ContentNode found')
                showToast({ type: 'info', message: 'Source node ID not found. Opening editor without chat history.' })
                setSourceNode(null)
                setShowWidgetDialog(true)
                return
            }

            // Fetch source ContentNode
            try {
                const response = await contentNodesAPI.get(sourceContentNodeId)
                setSourceNode(response.data)
                setShowWidgetDialog(true)
            } catch (error: any) {
                if (error.response?.status === 404) {
                    console.warn('Source node not found (404), opening editor without history')
                    showToast({ type: 'info', message: 'Source node was deleted. Opening editor without chat history.' })
                    setSourceNode(null)
                    setShowWidgetDialog(true)
                } else {
                    throw error
                }
            }
        } catch (error) {
            console.error('Failed to load source node:', error)
            showToast({ type: 'error', message: 'Failed to open widget editor' })
        }
    }

    // Create sandboxed iframe content
    useEffect(() => {
        if (!iframeRef.current || !node.html_code) return

        const iframe = iframeRef.current

        const authToken = localStorage.getItem('token') || ''

        // API script to inject (with cross-filter support)
        const sourceContentNodeId = node.config?.sourceContentNodeId
        const filteredEntry = sourceContentNodeId && filteredNodeData ? filteredNodeData[sourceContentNodeId] : null
        const precomputedTables = filteredEntry?.tables || undefined
        const dataStack = getDataStack(node.id)
        // Полные данные для highlight: стек виджета или initiator_full_data от бэкенда (для виджета-инициатора).
        const fullEntry = sourceContentNodeId ? initiatorFullNodeData[sourceContentNodeId] : null
        const fullTablesForHighlight =
            dataStack.length > 0 ? dataStack[dataStack.length - 1].tables : (fullEntry?.tables ?? filteredEntry?.tables ?? [])
        const filteredTablesForHighlight =
            fullTablesForHighlight.length > 0 && activeFilters
                ? applyFiltersToTables(fullTablesForHighlight, activeFilters)
                : undefined
        const activeFiltersParam = getFiltersQueryParam()
        const apiScript = sourceContentNodeId ? buildWidgetApiScript({
            contentNodeId: sourceContentNodeId,
            authToken,
            autoRefresh: node.auto_refresh || false,
            refreshInterval: node.refresh_interval || 5000,
            widgetId: node.id,
            activeFilters: activeFiltersParam || undefined,
            precomputedTables,
            dataStack: dataStack.length ? dataStack : undefined,
            filteredTablesForHighlight,
        }) : '';

        // Build HTML: detect if html_code is a full HTML document
        let fullHtml: string;
        const htmlCode = unescapeWidgetHtml(node.html_code || '');
        const isFullHtmlDoc = htmlCode.trim().toLowerCase().startsWith('<!doctype') || htmlCode.trim().toLowerCase().startsWith('<html');

        if (isFullHtmlDoc) {
            // Full HTML document — inject apiScript into <head>
            fullHtml = injectApiScript(htmlCode, apiScript);
        } else {
            // Legacy format: html fragment — wrap in full document
            fullHtml = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    ${apiScript}
    <style>
        body {
            margin: 0;
            padding: 8px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            overflow: auto;
        }
        ${node.css_code || ''}
    </style>
</head>
<body>
    ${htmlCode}
    ${node.js_code ? `<script>${node.js_code}</script>` : ''}
</body>
</html>
`;
        }
        iframe.srcdoc = fullHtml
    }, [node.html_code, node.css_code, node.js_code, node.auto_refresh, node.refresh_interval, refreshKey])

    // Create fullscreen iframe content (same logic as regular iframe)
    useEffect(() => {
        if (!isFullscreen || !fullscreenIframeRef.current || !node.html_code) return

        const iframe = fullscreenIframeRef.current

        const authToken = localStorage.getItem('token') || ''

        // API script to inject (same as regular iframe, with cross-filter support)
        const sourceContentNodeId = node.config?.sourceContentNodeId
        const filteredEntry = sourceContentNodeId && filteredNodeData ? filteredNodeData[sourceContentNodeId] : null
        const precomputedTables = filteredEntry?.tables || undefined
        const dataStackFullscreen = getDataStack(node.id)
        const fullEntryFullscreen = sourceContentNodeId ? initiatorFullNodeData[sourceContentNodeId] : null
        const fullTablesForHighlightFullscreen =
            dataStackFullscreen.length > 0 ? dataStackFullscreen[dataStackFullscreen.length - 1].tables : (fullEntryFullscreen?.tables ?? filteredEntry?.tables ?? [])
        const filteredTablesForHighlightFullscreen =
            fullTablesForHighlightFullscreen.length > 0 && activeFilters
                ? applyFiltersToTables(fullTablesForHighlightFullscreen, activeFilters)
                : undefined
        const activeFiltersParamFullscreen = getFiltersQueryParam()
        const apiScript = sourceContentNodeId ? buildWidgetApiScript({
            contentNodeId: sourceContentNodeId,
            authToken,
            autoRefresh: node.auto_refresh || false,
            refreshInterval: node.refresh_interval || 5000,
            widgetId: node.id,
            activeFilters: activeFiltersParamFullscreen || undefined,
            precomputedTables,
            dataStack: dataStackFullscreen.length ? dataStackFullscreen : undefined,
            filteredTablesForHighlight: filteredTablesForHighlightFullscreen,
        }) : '';

        // Build HTML: detect if html_code is a full HTML document
        let fullHtml: string;
        const htmlCode = unescapeWidgetHtml(node.html_code || '');
        const isFullHtmlDoc = htmlCode.trim().toLowerCase().startsWith('<!doctype') || htmlCode.trim().toLowerCase().startsWith('<html');

        if (isFullHtmlDoc) {
            // Full HTML document — inject apiScript into <head>
            fullHtml = injectApiScript(htmlCode, apiScript);
        } else {
            // Legacy format: html fragment — wrap in full document
            fullHtml = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    ${apiScript}
    <style>
        body {
            margin: 0;
            padding: 16px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            overflow: auto;
        }
        ${node.css_code || ''}
    </style>
</head>
<body>
    ${htmlCode}
    ${node.js_code ? `<script>${node.js_code}</script>` : ''}
</body>
</html>
`;
        }
        iframe.srcdoc = fullHtml
    }, [node.html_code, node.css_code, node.js_code, node.auto_refresh, node.refresh_interval, refreshKey, isFullscreen])

    return (
        <>
            <NodeResizer
                isVisible={selected}
                minWidth={200}
                minHeight={150}
                lineStyle={{ borderWidth: 0 }}
                handleStyle={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    backgroundColor: 'hsl(var(--background))',
                    border: '2px solid #a855f7',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
                }}
            />
            <div
                className="bg-card border border-border rounded-xl overflow-hidden transition-shadow duration-200"
                style={{
                    width: nodeWidth,
                    height: nodeHeight,
                    boxShadow: selected
                        ? '0 0 0 2px hsl(263 70% 50%), 0 8px 24px -4px rgba(0,0,0,0.12), 0 4px 8px -2px rgba(0,0,0,0.06)'
                        : '0 4px 12px -2px rgba(0,0,0,0.08), 0 2px 6px -2px rgba(0,0,0,0.04)',
                }}
            >
                {/* Header */}
                <div className="bg-gradient-to-r from-purple-600 to-purple-500 text-white px-3 py-2.5 flex items-center gap-2.5 justify-between shadow-sm">
                    <div className="flex items-center gap-2.5 flex-1 min-w-0">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white/15">
                            <HeaderIcon className="h-3.5 w-3.5" />
                        </div>
                        {isEditingName ? (
                            <Input
                                value={tempName}
                                onChange={(e) => setTempName(e.target.value)}
                                onBlur={handleSaveName}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleSaveName()
                                    if (e.key === 'Escape') handleCancelEditName()
                                }}
                                className="h-7 text-sm font-medium bg-white/95 text-foreground border-0 rounded-md focus-visible:ring-2 focus-visible:ring-white/50"
                                autoFocus
                                onClick={(e) => e.stopPropagation()}
                            />
                        ) : (
                            <span
                                className="text-sm font-medium truncate tracking-tight"
                                title={node.name}
                                onDoubleClick={handleStartEditName}
                            >
                                {node.name}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-0.5">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-white/90 hover:text-white hover:bg-white/15 rounded-md transition-colors"
                            onClick={(e) => {
                                e.stopPropagation()
                                setIsFullscreen(true)
                            }}
                            title="Развернуть на полный экран"
                        >
                            <Maximize className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-white/90 hover:text-white hover:bg-white/15 rounded-md transition-colors"
                            onClick={(e) => {
                                e.stopPropagation()
                                setRefreshKey(prev => prev + 1)
                            }}
                            title="Обновить данные"
                        >
                            <RefreshCw className="h-3.5 w-3.5" />
                        </Button>
                        {isAIGenerated && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-white/90 hover:text-white hover:bg-white/15 rounded-md transition-colors"
                                onClick={(e) => {
                                    e.stopPropagation()
                                    handleEdit()
                                }}
                                title="Редактировать визуализацию"
                            >
                                <Settings className="h-3.5 w-3.5" />
                            </Button>
                        )}
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-white/90 hover:text-white hover:bg-white/15 rounded-md transition-colors"
                                    onClick={(e) => e.stopPropagation()}
                                >
                                    <MoreVertical className="h-3.5 w-3.5" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                                <DropdownMenuItem onClick={handleStartEditName}>
                                    <Edit2 className="h-4 w-4 mr-2" />
                                    Переименовать
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={toggleAutoRefresh}>
                                    {node.auto_refresh ? (
                                        <>
                                            <TimerOff className="h-4 w-4 mr-2" />
                                            Отключить автообновление
                                        </>
                                    ) : (
                                        <>
                                            <Timer className="h-4 w-4 mr-2" />
                                            Включить автообновление
                                        </>
                                    )}
                                </DropdownMenuItem>
                                {node.auto_refresh && (
                                    <DropdownMenuItem onClick={() => {
                                        setTempInterval((node.refresh_interval || 5000) / 1000)
                                        setShowIntervalDialog(true)
                                    }}>
                                        <Settings className="h-4 w-4 mr-2" />
                                        Настроить интервал
                                    </DropdownMenuItem>
                                )}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </div>

                {/* Widget Preview - Sandboxed iframe */}
                <div
                    className="p-0 flex items-center justify-center bg-muted/20 relative overflow-hidden"
                    style={{ height: initiatorConditions.length > 0 ? 'calc(100% - 44px - 36px)' : 'calc(100% - 44px)' }}
                >
                    {node.html_code ? (
                        <iframe
                            key={refreshKey}
                            ref={iframeRef}
                            className="w-full h-full border-0 pointer-events-auto"
                            style={{
                                pointerEvents: selected ? 'none' : 'auto'
                            }}
                            title={`Widget: ${node.name}`}
                        />
                    ) : (
                        <div className="text-center text-muted-foreground p-6">
                            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-muted/60">
                                <Code className="h-6 w-6 opacity-60" />
                            </div>
                            <p className="text-sm font-medium">Нет визуализации</p>
                            {node.description && (
                                <p className="text-xs mt-1.5 text-muted-foreground/80 max-w-[200px] mx-auto leading-relaxed" title={node.description}>
                                    {node.description}
                                </p>
                            )}
                        </div>
                    )}

                    {/* Auto-refresh indicator */}
                    {node.auto_refresh && node.refresh_interval && (
                        <div className="absolute top-2 right-2 flex items-center gap-1 rounded-full bg-background/80 dark:bg-background/90 backdrop-blur-sm text-[10px] font-medium text-muted-foreground px-2 py-1 border border-border/60 shadow-sm">
                            <Timer className="h-2.5 w-2.5 text-purple-500" />
                            {node.refresh_interval / 1000}s
                        </div>
                    )}
                </div>

                {/* Мини-фильтр: условия, инициированные этим виджетом */}
                {initiatorConditions.length > 0 && (
                    <div
                        className="flex items-center gap-1 px-2 py-1.5 border-t bg-muted/30 flex-wrap"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <Filter className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        {initiatorConditions.map((c) => {
                            const dim = dimensions.find((d) => d.name === c.dim)
                            const displayName = dim?.display_name || c.dim
                            const valStr =
                                c.value === null || c.value === undefined
                                    ? '—'
                                    : Array.isArray(c.value)
                                        ? (c.value as unknown[]).join(', ')
                                        : String(c.value)
                            return (
                                <span
                                    key={c.dim}
                                    className="inline-flex items-center gap-1 rounded-md bg-purple-500/15 text-purple-700 dark:text-purple-300 px-1.5 py-0.5 text-[10px] max-w-[120px]"
                                >
                                    <span className="truncate font-medium">{displayName}</span>
                                    <span className="text-muted-foreground">{operatorLabel(c.op)}</span>
                                    <span className="truncate">{valStr}</span>
                                    <button
                                        type="button"
                                        className="ml-0.5 p-0.5 rounded hover:bg-purple-500/20 transition-colors"
                                        onClick={(e) => {
                                            e.stopPropagation()
                                            removeCondition(c.dim)
                                        }}
                                        title="Убрать фильтр"
                                    >
                                        <X className="h-2.5 w-2.5" />
                                    </button>
                                </span>
                            )
                        })}
                    </div>
                )}

                {/* Connection handle */}
                <Handle
                    type="target"
                    position={Position.Top}
                    id="visualize"
                    style={{
                        width: 12,
                        height: 12,
                        backgroundColor: '#7c3aed',
                        border: '2px solid hsl(var(--background))',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                    }}
                    isConnectable={false}
                />
            </div>

            {/* Interval Settings Dialog */}
            <Dialog open={showIntervalDialog} onOpenChange={setShowIntervalDialog}>
                <DialogContent onClick={(e) => e.stopPropagation()}>
                    <DialogHeader>
                        <DialogTitle>Настройка интервала автообновления</DialogTitle>
                    </DialogHeader>
                    <div className="py-4">
                        <Label htmlFor="interval-input" className="text-sm">
                            Интервал (секунды):
                        </Label>
                        <Input
                            id="interval-input"
                            type="number"
                            min="1"
                            max="300"
                            value={tempInterval}
                            onChange={(e) => setTempInterval(Math.max(1, parseInt(e.target.value) || 5))}
                            className="mt-2"
                        />
                        <p className="text-xs text-muted-foreground mt-2">
                            Рекомендуется: 1-60 секунд. Текущее: {tempInterval}s
                        </p>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowIntervalDialog(false)}>
                            Отмена
                        </Button>
                        <Button onClick={updateInterval} className="bg-purple-500 hover:bg-purple-600">
                            Применить
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Visualize Edit Dialog */}
            {sourceNode && (
                <WidgetDialog
                    open={showWidgetDialog}
                    onOpenChange={setShowWidgetDialog}
                    contentNode={sourceNode}
                    onVisualize={async () => { }}
                    onWidgetCreated={async () => {
                        await fetchWidgetNodes(node.board_id)
                        setRefreshKey(prev => prev + 1)
                    }}
                    initialMessages={node.config?.chatHistory || []}
                    initialAutoRefresh={node.auto_refresh}
                    initialRefreshInterval={(node.refresh_interval || 5000) / 1000}
                    widgetNodeId={node.id}
                    boardId={node.board_id}
                    initialHtmlCode={node.html_code}
                    initialWidgetName={node.name}
                />
            )}

            {/* Fullscreen Dialog */}
            <Dialog open={isFullscreen} onOpenChange={setIsFullscreen}>
                <DialogContent className="max-w-[95vw] max-h-[95vh] w-full h-full p-0 overflow-hidden" onClick={(e) => e.stopPropagation()}>
                    <DialogHeader className="bg-gradient-to-r from-purple-600 to-purple-500 text-white px-4 py-3 shadow-sm">
                        <div className="flex items-center justify-between w-full pr-8">
                            <DialogTitle className="flex items-center gap-2.5 font-medium">
                                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/15">
                                    <HeaderIcon className="h-4 w-4" />
                                </div>
                                {node.name}
                            </DialogTitle>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-white/90 hover:text-white hover:bg-white/15 rounded-md"
                                onClick={(e) => {
                                    e.stopPropagation()
                                    setRefreshKey(prev => prev + 1)
                                }}
                                title="Обновить данные"
                            >
                                <RefreshCw className="h-4 w-4" />
                            </Button>
                        </div>
                    </DialogHeader>
                    <div className="w-full h-[calc(95vh-56px)] bg-muted/20">
                        {node.html_code ? (
                            <iframe
                                ref={fullscreenIframeRef}
                                key={`fullscreen-${refreshKey}`}
                                className="w-full h-full border-0"
                                title={`Fullscreen Widget: ${node.name}`}
                            />
                        ) : (
                            <div className="flex items-center justify-center h-full text-muted-foreground">
                                <div className="text-center">
                                    <Code className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                    <p>Нет визуализации</p>
                                </div>
                            </div>
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </>
    )
})

WidgetNodeCard.displayName = 'WidgetNodeCard'
