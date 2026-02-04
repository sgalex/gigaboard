import { memo, useRef, useEffect, useState } from 'react'
import { Handle, Position, NodeProps, NodeResizer } from '@xyflow/react'
import { BarChart3, Code, Sparkles, RefreshCw, MoreVertical, Timer, TimerOff, Settings, Edit2, Maximize } from 'lucide-react'
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
import { WidgetDialog } from './WidgetDialog'

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

    // Trigger content reload when entering fullscreen
    useEffect(() => {
        if (isFullscreen) {
            // Force iframe recreation when entering fullscreen
            setRefreshKey(prev => prev + 1)
        }
    }, [isFullscreen])

    // Use React Flow dimensions (updated in real-time during resize) or fallback to node dimensions
    const nodeWidth = width ?? node.width ?? 320
    const nodeHeight = height ?? node.height ?? 240

    // Check if widget was AI-generated
    const isAIGenerated = !!node.generated_by

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
        const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
        if (!iframeDoc) return

        // Get source ContentNode ID from config
        const sourceContentNodeId = node.config?.sourceContentNodeId
        const authToken = localStorage.getItem('token') || ''

        // API script to inject
        const apiScript = sourceContentNodeId ? `
        <script>
            window.CONTENT_NODE_ID = '${sourceContentNodeId}';
            window.AUTH_TOKEN = '${authToken}';
            window.API_BASE = window.location.origin;
            window.AUTO_REFRESH_ENABLED = ${node.auto_refresh || false};
            window.REFRESH_INTERVAL = ${node.refresh_interval || 5000};
            
            window.fetchContentData = async function() {
                try {
                    const response = await fetch(\`\${window.API_BASE}/api/v1/content-nodes/\${window.CONTENT_NODE_ID}\`, {
                        headers: {
                            'Authorization': \`Bearer \${window.AUTH_TOKEN}\`,
                            'Content-Type': 'application/json'
                        }
                    });
                    if (!response.ok) throw new Error('Failed to fetch data');
                    const contentNode = await response.json();
                    return {
                        tables: contentNode.content?.tables || [],
                        text: contentNode.content?.text || '',
                        metadata: contentNode.metadata || {}
                    };
                } catch (error) {
                    console.error('Error fetching content data:', error);
                    return { tables: [], text: '', metadata: {} };
                }
            };
            
            window.getTable = async function(nameOrIndex) {
                const data = await window.fetchContentData();
                if (typeof nameOrIndex === 'number') return data.tables[nameOrIndex];
                return data.tables.find(t => t.name === nameOrIndex);
            };
            
            window.startAutoRefresh = function(callback, intervalMs) {
                if (!window.AUTO_REFRESH_ENABLED) {
                    console.log('Auto-refresh disabled');
                    return null;
                }
                const interval = intervalMs || window.REFRESH_INTERVAL || 5000;
                return setInterval(async () => {
                    const data = await window.fetchContentData();
                    callback(data);
                }, interval);
            };
            
            window.stopAutoRefresh = function(intervalId) {
                if (intervalId) clearInterval(intervalId);
            };
        </script>` : '';

        // Build complete HTML document with styles and script
        const fullHtml = `
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
    ${node.html_code}
    ${node.js_code ? `<script>${node.js_code}</script>` : ''}
</body>
</html>
`
        iframeDoc.open()
        iframeDoc.write(fullHtml)
        iframeDoc.close()
    }, [node.html_code, node.css_code, node.js_code, node.auto_refresh, node.refresh_interval, refreshKey])

    // Create fullscreen iframe content (same logic as regular iframe)
    useEffect(() => {
        if (!isFullscreen || !fullscreenIframeRef.current || !node.html_code) return

        const iframe = fullscreenIframeRef.current
        const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
        if (!iframeDoc) return

        // Get source ContentNode ID from config
        const sourceContentNodeId = node.config?.sourceContentNodeId
        const authToken = localStorage.getItem('token') || ''

        // API script to inject (same as regular iframe)
        const apiScript = sourceContentNodeId ? `
        <script>
            window.CONTENT_NODE_ID = '${sourceContentNodeId}';
            window.AUTH_TOKEN = '${authToken}';
            window.API_BASE = window.location.origin;
            window.AUTO_REFRESH_ENABLED = ${node.auto_refresh || false};
            window.REFRESH_INTERVAL = ${node.refresh_interval || 5000};
            
            window.fetchContentData = async function() {
                try {
                    const response = await fetch(\`\${window.API_BASE}/api/v1/content-nodes/\${window.CONTENT_NODE_ID}\`, {
                        headers: {
                            'Authorization': \`Bearer \${window.AUTH_TOKEN}\`,
                            'Content-Type': 'application/json'
                        }
                    });
                    if (!response.ok) throw new Error('Failed to fetch data');
                    const contentNode = await response.json();
                    return {
                        tables: contentNode.content?.tables || [],
                        text: contentNode.content?.text || '',
                        metadata: contentNode.metadata || {}
                    };
                } catch (error) {
                    console.error('Error fetching content data:', error);
                    return { tables: [], text: '', metadata: {} };
                }
            };
            
            window.getTable = async function(nameOrIndex) {
                const data = await window.fetchContentData();
                if (typeof nameOrIndex === 'number') return data.tables[nameOrIndex];
                return data.tables.find(t => t.name === nameOrIndex);
            };
            
            window.startAutoRefresh = function(callback, intervalMs) {
                if (!window.AUTO_REFRESH_ENABLED) {
                    console.log('Auto-refresh disabled');
                    return null;
                }
                const interval = intervalMs || window.REFRESH_INTERVAL || 5000;
                return setInterval(async () => {
                    const data = await window.fetchContentData();
                    callback(data);
                }, interval);
            };
            
            window.stopAutoRefresh = function(intervalId) {
                if (intervalId) clearInterval(intervalId);
            };
        </script>` : '';

        // Build complete HTML document with styles and script
        const fullHtml = `
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
    ${node.html_code}
    ${node.js_code ? `<script>${node.js_code}</script>` : ''}
</body>
</html>
`
        iframeDoc.open()
        iframeDoc.write(fullHtml)
        iframeDoc.close()
    }, [node.html_code, node.css_code, node.js_code, node.auto_refresh, node.refresh_interval, refreshKey, isFullscreen])

    return (
        <>
            <NodeResizer
                isVisible={selected}
                minWidth={200}
                minHeight={150}
                lineStyle={{ borderWidth: 0 }}
                handleStyle={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '2px',
                    backgroundColor: '#a855f7',
                    border: '2px solid white',
                }}
            />
            <div
                className="bg-background border-2 border-purple-500 rounded-lg shadow-lg overflow-hidden"
                style={{
                    width: nodeWidth,
                    height: nodeHeight,
                    boxShadow: selected
                        ? '0 0 0 4px rgba(168, 85, 247, 0.6), 0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                        : undefined,
                }}
            >
                {/* Header */}
                <div className="bg-purple-500 text-white px-3 py-2 flex items-center gap-2 justify-between">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                        <BarChart3 className="h-4 w-4 flex-shrink-0" />
                        {isEditingName ? (
                            <Input
                                value={tempName}
                                onChange={(e) => setTempName(e.target.value)}
                                onBlur={handleSaveName}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleSaveName()
                                    if (e.key === 'Escape') handleCancelEditName()
                                }}
                                className="h-6 text-sm font-medium bg-white text-black"
                                autoFocus
                                onClick={(e) => e.stopPropagation()}
                            />
                        ) : (
                            <span
                                className="text-sm font-medium truncate"
                                title={node.name}
                                onDoubleClick={handleStartEditName}
                            >
                                {node.name}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 hover:bg-purple-600 text-white"
                            onClick={(e) => {
                                e.stopPropagation()
                                setIsFullscreen(true)
                            }}
                            title="Развернуть на полный экран"
                        >
                            <Maximize className="h-4 w-4" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 hover:bg-purple-600 text-white"
                            onClick={(e) => {
                                e.stopPropagation()
                                setRefreshKey(prev => prev + 1)
                            }}
                            title="Обновить данные"
                        >
                            <RefreshCw className="h-4 w-4" />
                        </Button>
                        {isAIGenerated && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 hover:bg-purple-600 text-white"
                                onClick={(e) => {
                                    e.stopPropagation()
                                    handleEdit()
                                }}
                                title="Редактировать визуализацию"
                            >
                                <Settings className="h-4 w-4" />
                            </Button>
                        )}
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8 hover:bg-purple-600 text-white"
                                    onClick={(e) => e.stopPropagation()}
                                >
                                    <MoreVertical className="h-4 w-4" />
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
                <div className="p-0 h-[calc(100%-40px)] flex items-center justify-center bg-muted/30 relative overflow-hidden">
                    {node.html_code ? (
                        <iframe
                            ref={iframeRef}
                            className="w-full h-full border-0 pointer-events-auto"
                            style={{
                                pointerEvents: selected ? 'none' : 'auto'
                            }}
                            sandbox="allow-scripts allow-same-origin"
                            title={`Widget: ${node.name}`}
                        />
                    ) : (
                        <div className="text-center text-muted-foreground p-4">
                            <Code className="h-8 w-8 mx-auto mb-2 opacity-50" />
                            <p className="text-xs">No visualization</p>
                            {node.description && (
                                <p className="text-xs mt-1 opacity-70 max-w-xs" title={node.description}>
                                    {node.description}
                                </p>
                            )}
                        </div>
                    )}

                    {/* Auto-refresh indicator */}
                    {node.auto_refresh && node.refresh_interval && (
                        <div className="absolute top-1 right-1 bg-purple-500 text-white text-[10px] px-1.5 py-0.5 rounded">
                            Auto-refresh: {node.refresh_interval / 1000}s
                        </div>
                    )}
                </div>

                {/* Connection handles */}
                {/* Top handle for visualizations (connections from ContentNode) */}
                <Handle
                    type="target"
                    position={Position.Top}
                    id="visualize"
                    style={{ width: '10px', height: '10px', backgroundColor: '#a855f7' }}
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
                <DialogContent className="max-w-[95vw] max-h-[95vh] w-full h-full p-0" onClick={(e) => e.stopPropagation()}>
                    <DialogHeader className="bg-purple-500 text-white px-4 py-3">
                        <div className="flex items-center justify-between w-full pr-8">
                            <DialogTitle className="flex items-center gap-2">
                                <BarChart3 className="h-5 w-5" />
                                {node.name}
                            </DialogTitle>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 hover:bg-purple-600 text-white"
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
                    <div className="w-full h-[calc(95vh-60px)] bg-muted/30">
                        {node.html_code ? (
                            <iframe
                                ref={fullscreenIframeRef}
                                key={`fullscreen-${refreshKey}`}
                                className="w-full h-full border-0"
                                sandbox="allow-scripts allow-same-origin"
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
