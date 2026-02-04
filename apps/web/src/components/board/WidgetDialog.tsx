import { useState, useRef, useEffect } from 'react'
import Editor from '@monaco-editor/react'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Sparkles, Loader2, Send, Code, Eye, Save, RefreshCw, Trash2 } from 'lucide-react'
import { ContentNode } from '@/types'
import { cn } from '@/lib/utils'
import { contentNodesAPI, widgetNodesAPI, edgesAPI } from '@/services/api'
import { findOptimalNodePosition, convertNodesToBounds } from '@/lib/nodePositioning'
import { useBoardStore } from '@/store/boardStore'
import { SuggestionsPanel } from './SuggestionsPanel'

interface WidgetDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    contentNode: ContentNode
    onVisualize: (params: {
        user_prompt?: string
        auto_refresh?: boolean
    }) => Promise<void>
    onWidgetCreated?: () => void  // Callback to refresh board nodes
    initialMessages?: ChatMessage[]  // Restore chat history for editing
    initialAutoRefresh?: boolean  // Restore auto-refresh setting
    initialRefreshInterval?: number  // Restore interval (in seconds)
    widgetNodeId?: string  // If editing existing widget
    boardId?: string  // Board ID for updating widget
    initialHtmlCode?: string  // Current widget HTML code
    initialWidgetName?: string  // Current widget name
}

interface ChatMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: Date
}

interface VisualizationState {
    html: string
    css: string
    js: string
    description: string
    widget_code?: string  // Full HTML from GigaChat
    widget_name?: string  // Short name for widget
}

export const WidgetDialog = ({
    open,
    onOpenChange,
    contentNode,
    onVisualize,
    onWidgetCreated,
    initialMessages,
    initialAutoRefresh,
    initialRefreshInterval,
    widgetNodeId,
    boardId,
    initialHtmlCode,
    initialWidgetName,
}: WidgetDialogProps) => {
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
    const [inputValue, setInputValue] = useState('')
    const [isGenerating, setIsGenerating] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [autoRefresh, setAutoRefresh] = useState(true)
    const [refreshInterval, setRefreshInterval] = useState(5)
    const [currentVisualization, setCurrentVisualization] = useState<VisualizationState | null>(null)
    const [editedCode, setEditedCode] = useState<VisualizationState | null>(null)
    const [rightPanelTab, setRightPanelTab] = useState<'preview' | 'code'>('preview')
    const [iframeKey, setIframeKey] = useState(0)  // Key to force iframe recreation
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const iframeRef = useRef<HTMLIFrameElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    // Initialize or reset state when dialog opens
    useEffect(() => {
        if (!open) return

        if (widgetNodeId && initialHtmlCode) {
            // Edit mode: restore all data
            setChatMessages(initialMessages || [])
            setAutoRefresh(initialAutoRefresh ?? true)
            setRefreshInterval(initialRefreshInterval ?? 5)
            setCurrentVisualization({
                widget_name: initialWidgetName || 'Widget',
                widget_code: initialHtmlCode,
                html: '',
                css: '',
                js: '',
                description: 'Existing widget'
            })
            setEditedCode(null)
        } else {
            // Create mode: reset everything
            setChatMessages([])
            setInputValue('')
            setCurrentVisualization(null)
            setEditedCode(null)
            setAutoRefresh(true)
            setRefreshInterval(5)
            setRightPanelTab('preview')
        }
        setIframeKey(prev => prev + 1)
    }, [open, widgetNodeId, initialHtmlCode, initialWidgetName, initialMessages, initialAutoRefresh, initialRefreshInterval])

    // Auto-scroll chat to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [chatMessages])

    // Update iframe when visualization changes
    useEffect(() => {
        if (!iframeRef.current || !currentVisualization) return

        const code = editedCode || currentVisualization
        const iframe = iframeRef.current
        const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
        if (!iframeDoc) return

        // Get auth token for iframe API calls
        const authToken = localStorage.getItem('token') || ''
        const contentNodeId = contentNode.id

        // API script to inject into widget HTML
        const apiScript = `
        <script>
            // API Client for dynamic data access (injected by GigaBoard)
            window.CONTENT_NODE_ID = '${contentNodeId}';
            window.AUTH_TOKEN = '${authToken}';
            window.API_BASE = window.location.origin;
            window.AUTO_REFRESH_ENABLED = ${autoRefresh};
            window.REFRESH_INTERVAL = ${refreshInterval * 1000};
            
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
        </script>`;

        let fullHtml: string;

        // Check if we have full HTML (widget_code) or separate parts
        if (code.widget_code) {
            // GigaChat generated full HTML - inject API script after <head> or at start of <body>
            fullHtml = code.widget_code;
            if (fullHtml.includes('<head>')) {
                fullHtml = fullHtml.replace('<head>', '<head>' + apiScript);
            } else if (fullHtml.includes('<body>')) {
                fullHtml = fullHtml.replace('<body>', '<body>' + apiScript);
            } else {
                // Fallback: prepend script
                fullHtml = apiScript + fullHtml;
            }
        } else {
            // Legacy format: separate html/css/js parts
            const jsScript = code.js ? `<script>${code.js}</script>` : '';
            fullHtml = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    ${apiScript}
    <style>
        body { margin: 0; padding: 8px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; overflow: auto; }
        ${code.css || ''}
    </style>
</head>
<body>
    ${code.html || ''}
    ${jsScript}
</body>
</html>`;
        }

        iframeDoc.open()
        iframeDoc.write(fullHtml)
        iframeDoc.close()
    }, [currentVisualization, editedCode, autoRefresh, contentNode.id])

    // Handle send message
    const handleSendMessage = async (messageText?: string) => {
        const textToSend = messageText || inputValue.trim()
        if (!textToSend || isGenerating) return

        const userMessage: ChatMessage = {
            id: Date.now().toString(),
            role: 'user',
            content: textToSend,
            timestamp: new Date()
        }

        setChatMessages(prev => [...prev, userMessage])
        setInputValue('')
        setIsGenerating(true)

        try {
            // Build chat history including current message
            const fullChatHistory = [
                ...chatMessages.map(msg => ({
                    role: msg.role,
                    content: msg.content
                })),
                { role: userMessage.role, content: userMessage.content }
            ]

            // Call iterative visualization endpoint
            const response = await contentNodesAPI.visualizeIterative(contentNode.id, {
                user_prompt: userMessage.content,
                existing_html: currentVisualization?.html,
                existing_css: currentVisualization?.css,
                existing_js: currentVisualization?.js,
                existing_widget_code: currentVisualization?.widget_code,
                chat_history: fullChatHistory
            })

            const data = response.data

            // Add AI response to chat
            const aiMessage: ChatMessage = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.description || 'Визуализация создана',
                timestamp: new Date()
            }
            setChatMessages(prev => [...prev, aiMessage])

            // Update visualization (support both widget_code and legacy format)
            setCurrentVisualization({
                html: data.html_code || '',
                css: data.css_code || '',
                js: data.js_code || '',
                description: data.description,
                widget_code: data.widget_code,
                widget_name: data.widget_name
            })

            // Force iframe recreation to kill old intervals/state
            setIframeKey(prev => prev + 1)

            // Reset edited code when new version arrives
            setEditedCode(null)

        } catch (error) {
            console.error('Visualization generation failed:', error)
            const errorMessage: ChatMessage = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: '❌ Ошибка генерации визуализации. Попробуйте ещё раз.',
                timestamp: new Date()
            }
            setChatMessages(prev => [...prev, errorMessage])
        } finally {
            setIsGenerating(false)
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSendMessage()
        }
    }

    // Auto-resize textarea
    const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setInputValue(e.target.value)

        // Auto-resize
        const textarea = e.target
        textarea.style.height = 'auto'
        textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`
    }

    // Apply manual code edits
    const handleApplyCode = () => {
        if (!currentVisualization) return
        // editedCode state triggers iframe update via useEffect
    }

    // Save to board
    const handleSaveToBoard = async () => {
        if (!currentVisualization || isSaving) return

        setIsSaving(true)
        try {
            const code = editedCode || currentVisualization

            if (widgetNodeId && boardId) {
                // Update existing widget
                await widgetNodesAPI.update(boardId, widgetNodeId, {
                    html_code: code.widget_code || '',
                    css_code: code.css || '',
                    js_code: code.js || '',
                    config: {
                        sourceContentNodeId: contentNode.id,
                        chatHistory: chatMessages
                    },
                    auto_refresh: autoRefresh,
                    refresh_interval: autoRefresh ? refreshInterval * 1000 : undefined,
                })
            } else {
                // Create new WidgetNode with smart positioning
                const targetWidth = 400
                const targetHeight = 300

                // Get all existing nodes for collision detection
                const { widgetNodes, contentNodes, sourceNodes, commentNodes } = useBoardStore.getState()
                console.log('🔍 Checking collision with existing nodes:', {
                    widgetNodes: widgetNodes.length,
                    contentNodes: contentNodes.length,
                    sourceNodes: sourceNodes.length,
                    commentNodes: commentNodes.length
                })

                const allExistingNodes = [
                    ...widgetNodes.map(n => ({
                        id: n.id,
                        position: { x: n.x || 0, y: n.y || 0 },
                        width: n.width || 400,
                        height: n.height || 300
                    })),
                    ...contentNodes.map(n => ({
                        id: n.id,
                        position: { x: n.position?.x || 0, y: n.position?.y || 0 },
                        width: n.width || 320,
                        height: n.height || 200
                    })),
                    ...sourceNodes.map(n => ({
                        id: n.id,
                        position: { x: n.position?.x || 0, y: n.position?.y || 0 },
                        width: n.width || 280,
                        height: n.height || 150
                    })),
                    ...commentNodes.map(n => ({
                        id: n.id,
                        position: { x: n.x || 0, y: n.y || 0 },
                        width: n.width || 300,
                        height: n.height || 180
                    }))
                ]

                // Find optimal position using smart algorithm
                const optimalPosition = findOptimalNodePosition({
                    sourceNode: {
                        x: contentNode.position?.x || 0,
                        y: contentNode.position?.y || 0,
                        width: contentNode.width || 320,
                        height: contentNode.height || 200
                    },
                    targetWidth,
                    targetHeight,
                    existingNodes: convertNodesToBounds(allExistingNodes),
                    connectionType: 'visualization'
                })

                console.log('📍 Optimal position calculated:', optimalPosition)

                const response = await widgetNodesAPI.create(contentNode.board_id, {
                    name: code.widget_name || `Visualization ${contentNode.id.slice(0, 8)}`,
                    description: code.description || 'AI-generated visualization',
                    html_code: code.widget_code || '',
                    css_code: code.css || '',
                    js_code: code.js || '',
                    config: {
                        sourceContentNodeId: contentNode.id,  // Save source for data fetching
                        chatHistory: chatMessages  // Save chat history for future editing
                    },
                    auto_refresh: autoRefresh,
                    refresh_interval: autoRefresh ? refreshInterval * 1000 : undefined,
                    generated_by: 'reporter_agent',
                    generation_prompt: chatMessages.length > 0 ? chatMessages[0].content : 'visualize data',
                    // Use smart positioning algorithm
                    x: optimalPosition.x,
                    y: optimalPosition.y,
                    width: targetWidth,
                    height: targetHeight
                })
                const newWidgetNode = response.data

                // Create edge: ContentNode -> WidgetNode
                await edgesAPI.create(contentNode.board_id, {
                    source_node_id: contentNode.id,
                    target_node_id: newWidgetNode.id,
                    source_node_type: 'ContentNode',
                    target_node_type: 'WidgetNode',
                    edge_type: 'VISUALIZATION' as any
                })
            }

            // Refresh board to show updated/new widget
            onWidgetCreated?.()

            onOpenChange(false)
        } catch (error) {
            console.error('Failed to save widget:', error)
            // TODO: Show error toast
        } finally {
            setIsSaving(false)
        }
    }

    // Helper function to render a single table
    const renderTable = (table: ContentNode['content']['tables'][0], index: number) => (
        <div key={index} className="border rounded p-2 space-y-2">
            <div className="text-xs font-medium">
                {table.name} <span className="text-muted-foreground">({table.row_count} строк)</span>
            </div>
            <div className="border rounded overflow-x-auto max-h-[120px] overflow-y-auto">
                <table className="w-full text-[10px]">
                    <thead className="sticky top-0 bg-muted">
                        <tr>
                            {table.columns.slice(0, 4).map((col, idx) => {
                                // Handle both old (string) and new (object) column formats
                                const colName = typeof col === 'string' ? col : col.name || String(col)
                                return (
                                    <th key={idx} className="px-1 py-0.5 text-left font-medium">
                                        {colName}
                                    </th>
                                )
                            })}
                            {table.columns.length > 4 && <th className="px-1 py-0.5">...</th>}
                        </tr>
                    </thead>
                    <tbody>
                        {table.rows.slice(0, 3).map((row, rowIdx) => {
                            // Handle both old (array) and new (object) row formats
                            const rowValues = Array.isArray(row) ? row : row.values || []
                            return (
                                <tr key={rowIdx} className="border-t">
                                    {rowValues.slice(0, 4).map((cell, cellIdx) => (
                                        <td key={cellIdx} className="px-1 py-0.5">
                                            {cell !== null && cell !== undefined ? String(cell).substring(0, 20) : '-'}
                                        </td>
                                    ))}
                                    {rowValues.length > 4 && <td className="px-1 py-0.5">...</td>}
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    )

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-[1400px] h-[90vh] p-0 flex flex-col">
                <DialogHeader className="px-6 py-1.5 border-b shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-sm leading-tight">
                        <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                        Интерактивный редактор визуализаций
                    </DialogTitle>
                    <DialogDescription className="text-xs leading-tight mt-0.5">
                        Создайте визуализацию с помощью AI или отредактируйте код вручную
                    </DialogDescription>
                </DialogHeader>

                <div className="flex flex-1 min-h-0">
                    {/* Left Panel - Data & Chat */}
                    <div className="w-[40%] border-r flex flex-col">
                        {/* Data Source Preview */}
                        <div className="flex-1 p-2 border-b overflow-y-auto max-h-[30%]">
                            <div className="text-xs font-medium mb-1">📊 Данные источника:</div>
                            <div className="space-y-2">
                                {contentNode.content?.tables && contentNode.content.tables.length > 0 ? (
                                    contentNode.content.tables.map((table, index) => renderTable(table, index))
                                ) : (
                                    <div className="text-xs text-muted-foreground">Нет данных для отображения</div>
                                )}
                            </div>
                        </div>

                        {/* Chat Messages */}
                        <div className="flex items-center justify-between px-3 pt-2 pb-1">
                            <span className="text-xs font-medium text-muted-foreground">Диалог с AI</span>
                            {chatMessages.length > 0 && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 px-2 text-xs text-muted-foreground hover:text-destructive"
                                    onClick={() => {
                                        setChatMessages([])
                                        setCurrentVisualization(null)
                                        setEditedCode(null)
                                        setIframeKey(prev => prev + 1)
                                    }}
                                >
                                    <Trash2 className="w-3 h-3 mr-1" />
                                    Очистить
                                </Button>
                            )}
                        </div>
                        <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-2">
                            {chatMessages.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                                    <Sparkles className="w-10 h-10 mb-3 text-purple-500/30" />
                                    <p className="text-sm">
                                        Опишите какую визуализацию вы хотите создать
                                    </p>
                                    <p className="text-xs mt-2">
                                        Например: "Создай bar chart" или "Покажи топ-10"
                                    </p>
                                </div>
                            ) : (
                                chatMessages.map((msg) => (
                                    <div
                                        key={msg.id}
                                        className={cn(
                                            'flex',
                                            msg.role === 'user' ? 'justify-end' : 'justify-start'
                                        )}
                                    >
                                        <div
                                            className={cn(
                                                'max-w-[85%] rounded-lg px-3 py-2 text-sm',
                                                msg.role === 'user'
                                                    ? 'bg-purple-500 text-white'
                                                    : 'bg-muted'
                                            )}
                                        >
                                            {msg.content}
                                        </div>
                                    </div>
                                ))
                            )}
                            {isGenerating && (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    AI создаёт визуализацию...
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* AI Suggestions Panel */}
                        <div className="border-t overflow-y-auto max-h-[120px]">
                            <SuggestionsPanel
                                contentNodeId={contentNode.id}
                                chatHistory={chatMessages.map(msg => ({
                                    role: msg.role,
                                    content: msg.content
                                }))}
                                currentWidgetCode={currentVisualization?.widget_code}
                                onSuggestionClick={(prompt) => {
                                    // Send prompt directly to AI
                                    handleSendMessage(prompt)
                                }}
                            />
                        </div>

                        {/* Chat Input */}
                        <div className="p-2 border-t">
                            <div className="flex gap-2 items-end">
                                <Textarea
                                    ref={textareaRef}
                                    value={inputValue}
                                    onChange={handleInputChange}
                                    onKeyDown={handleKeyDown}
                                    placeholder="Опишите визуализацию или корректировку..."
                                    className="min-h-[32px] py-1.5 px-2 resize-none text-sm overflow-hidden"
                                    style={{ height: '32px' }}
                                    disabled={isGenerating}
                                    rows={1}
                                />
                                <Button
                                    onClick={handleSendMessage}
                                    disabled={!inputValue.trim() || isGenerating}
                                    size="icon"
                                    className="h-[32px] w-[32px] shrink-0 bg-purple-500 hover:bg-purple-600"
                                >
                                    {isGenerating ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : (
                                        <Send className="w-5 h-5" />
                                    )}
                                </Button>
                            </div>
                        </div>
                    </div>

                    {/* Right Panel - Preview & Code with Tabs */}
                    <div className="w-[60%] flex flex-col">
                        {/* Widget Name & Tab Switcher */}
                        <div className="px-3 pt-2 pb-1 border-b">
                            {currentVisualization?.widget_name && (
                                <div className="text-sm font-medium mb-1.5 flex items-center gap-2">
                                    <Sparkles className="w-3.5 h-3.5 text-purple-500" />
                                    {currentVisualization.widget_name}
                                </div>
                            )}
                            <Tabs value={rightPanelTab} onValueChange={(v) => setRightPanelTab(v as 'preview' | 'code')}>
                                <TabsList className="h-8 w-full grid grid-cols-2">
                                    <TabsTrigger value="preview" className="flex items-center gap-1.5 text-xs h-7">
                                        <Eye className="w-3.5 h-3.5" />
                                        Предпросмотр
                                    </TabsTrigger>
                                    <TabsTrigger value="code" className="flex items-center gap-1.5 text-xs h-7">
                                        <Code className="w-3.5 h-3.5" />
                                        Код виджета
                                    </TabsTrigger>
                                </TabsList>
                            </Tabs>
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 p-3 flex flex-col overflow-hidden">
                            {/* Preview Panel - Hidden when not active */}
                            <div className={cn("flex-1 flex flex-col", rightPanelTab !== 'preview' && "hidden")}>
                                <div className="flex-1 border rounded-lg overflow-hidden bg-white">
                                    {currentVisualization ? (
                                        <iframe
                                            key={iframeKey}
                                            ref={iframeRef}
                                            className="w-full h-full border-0"
                                            sandbox="allow-scripts allow-same-origin"
                                            title="Visualization Preview"
                                        />
                                    ) : (
                                        <div className="flex items-center justify-center h-full text-muted-foreground">
                                            <div className="text-center">
                                                <Eye className="w-12 h-12 mx-auto mb-2 opacity-30" />
                                                <p className="text-sm">Визуализация появится здесь</p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Code Panel - Hidden when not active */}
                            <div className={cn("flex-1 flex flex-col", rightPanelTab !== 'code' && "hidden")}>
                                {editedCode && (
                                    <div className="flex items-center justify-end mb-2">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={handleApplyCode}
                                        >
                                            Применить изменения
                                        </Button>
                                    </div>
                                )}
                                {currentVisualization ? (
                                    <div className="flex-1 flex flex-col">
                                        <div className="text-xs font-medium mb-2">Widget HTML</div>
                                        <div className="flex-1 border rounded-lg overflow-hidden">
                                            <Editor
                                                height="100%"
                                                language="html"
                                                value={editedCode?.widget_code || currentVisualization.widget_code || ''}
                                                onChange={(value) => setEditedCode(prev => ({
                                                    html: '',
                                                    css: '',
                                                    js: '',
                                                    description: prev?.description || currentVisualization?.description || '',
                                                    widget_code: value || ''
                                                }))}
                                                options={{
                                                    minimap: { enabled: false },
                                                    fontSize: 12,
                                                    lineNumbers: 'on',
                                                    scrollBeyondLastLine: false,
                                                }}
                                            />
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex-1 border rounded-lg flex items-center justify-center text-muted-foreground">
                                        <div className="text-center">
                                            <Code className="w-12 h-12 mx-auto mb-2 opacity-30" />
                                            <p className="text-sm">Код появится после создания визуализации</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                <DialogFooter className="px-6 py-1.5 border-t shrink-0">
                    <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2">
                                <Switch
                                    id="auto-refresh"
                                    checked={autoRefresh}
                                    onCheckedChange={setAutoRefresh}
                                />
                                <Label htmlFor="auto-refresh" className="text-xs cursor-pointer">
                                    Автообновление
                                </Label>
                            </div>
                            {autoRefresh && (
                                <div className="flex items-center gap-2">
                                    <Label htmlFor="refresh-interval" className="text-xs whitespace-nowrap">
                                        Интервал (сек):
                                    </Label>
                                    <Input
                                        id="refresh-interval"
                                        type="number"
                                        min="1"
                                        max="300"
                                        value={refreshInterval}
                                        onChange={(e) => setRefreshInterval(Math.max(1, parseInt(e.target.value) || 5))}
                                        className="h-7 w-16 text-xs"
                                    />
                                </div>
                            )}
                        </div>
                        <div className="flex gap-2">
                            <Button
                                variant="outline"
                                onClick={() => onOpenChange(false)}
                            >
                                Отмена
                            </Button>
                            <Button
                                onClick={handleSaveToBoard}
                                disabled={!currentVisualization || isSaving}
                                className="bg-purple-500 hover:bg-purple-600"
                            >
                                {isSaving ? (
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <Save className="w-4 h-4 mr-2" />
                                )}
                                {isSaving ? 'Сохранение...' : 'Сохранить на доску'}
                            </Button>
                        </div>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
