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
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Code, Loader2, Send, Eye, Save, Trash2, Sparkles } from 'lucide-react'
import { ContentNode } from '@/types'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'
import { TransformSuggestionsPanel } from './TransformSuggestionsPanel'

interface TransformDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    sourceNode?: ContentNode
    sourceNodes?: ContentNode[]
    onTransform: (code: string, transformationId: string, description?: string) => Promise<void>
    // Edit mode
    initialMessages?: ChatMessage[]
    initialCode?: string
    initialTransformationId?: string
}

interface ChatMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: Date
}

interface TransformationState {
    code: string
    description: string
    transformationId: string
    previewData?: PreviewData
    error?: string
}

interface PreviewData {
    tables: Array<{
        name: string
        columns: string[]
        rows: Array<Array<any>>
        row_count: number
        preview_row_count: number
    }>
    execution_time_ms: number
}

export function TransformDialog({
    open,
    onOpenChange,
    sourceNode,
    sourceNodes,
    onTransform,
    initialMessages,
    initialCode,
    initialTransformationId,
}: TransformDialogProps) {
    console.log('TransformDialog render, open:', open, 'sourceNode:', sourceNode, 'sourceNodes:', sourceNodes)
    console.log('📦 Initial props:', {
        hasInitialMessages: !!initialMessages,
        messagesCount: initialMessages?.length,
        hasInitialCode: !!initialCode,
        codeLength: initialCode?.length,
        initialTransformationId
    })

    // Normalize to array - check length, not just truthiness
    const nodes = (sourceNodes && sourceNodes.length > 0) ? sourceNodes : (sourceNode ? [sourceNode] : [])
    const primaryNode = nodes[0]
    console.log('nodes array:', nodes, 'primaryNode:', primaryNode)

    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
    const [inputValue, setInputValue] = useState('')
    const [isGenerating, setIsGenerating] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [currentTransformation, setCurrentTransformation] = useState<TransformationState | null>(null)
    const [editedCode, setEditedCode] = useState<string | null>(null)
    const [rightPanelTab, setRightPanelTab] = useState<'preview' | 'code'>('preview')
    const [selectedSourceTableIndex, setSelectedSourceTableIndex] = useState(0)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const previewLoadedRef = useRef<boolean>(false)
    const token = useAuthStore((state) => state.token)

    // Calculate source data info
    const allTables = nodes.flatMap(n => n.content?.tables || [])
    const tableCount = allTables.length
    const totalRows = allTables.reduce((sum, t) => sum + (t.row_count || 0), 0)

    // Initialize or reset state when dialog opens
    useEffect(() => {
        if (!open) {
            previewLoadedRef.current = false
            return
        }

        // Always reset isGenerating when dialog opens
        setIsGenerating(false)

        if (initialCode && initialTransformationId) {
            // Edit mode: restore data
            console.log('📝 Edit mode initialization:', {
                codeLength: initialCode.length,
                transformationId: initialTransformationId,
                messagesCount: initialMessages?.length || 0
            })
            setChatMessages(initialMessages || [])
            setCurrentTransformation({
                code: initialCode,
                description: 'Existing transformation',
                transformationId: initialTransformationId,
            })
            setEditedCode(null)
            previewLoadedRef.current = false // Reset flag to trigger preview load
        } else {
            // Create mode: reset
            setChatMessages([])
            setInputValue('')
            setCurrentTransformation(null)
            setEditedCode(null)
            setRightPanelTab('preview')
            previewLoadedRef.current = false
        }
    }, [open, initialCode, initialTransformationId, initialMessages])

    // Auto-execute initial code to load preview
    useEffect(() => {
        if (!open || !initialCode || !initialTransformationId || !primaryNode) {
            console.log('⏭️ Skipping auto-execute:', {
                open,
                hasInitialCode: !!initialCode,
                hasInitialTransformationId: !!initialTransformationId,
                hasPrimaryNode: !!primaryNode
            })
            return
        }

        // Check if preview is already loaded
        if (previewLoadedRef.current) {
            console.log('✅ Preview already loaded, skipping auto-execute')
            return
        }

        console.log('🔄 Auto-executing initial code for preview...', {
            nodeId: primaryNode.id,
            codeLength: initialCode.length,
            transformationId: initialTransformationId,
            currentTransformationSet: !!currentTransformation
        })

        const loadPreview = async () => {
            setIsGenerating(true)
            try {
                const response = await fetch(`/api/v1/content-nodes/${primaryNode.id}/transform/test`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`,
                    },
                    body: JSON.stringify({
                        code: initialCode,
                        transformation_id: initialTransformationId,
                    }),
                })

                if (!response.ok) {
                    const errorText = await response.text()
                    console.error('❌ Preview request failed:', response.status, errorText)
                    throw new Error(`Preview failed: ${response.statusText}`)
                }

                const result = await response.json()
                console.log('✅ Preview loaded:', {
                    tables: result.tables?.length,
                    executionTime: result.execution_time_ms
                })

                setCurrentTransformation(prev => {
                    if (!prev) {
                        console.warn('⚠️ No currentTransformation to update, creating new')
                        return {
                            code: initialCode,
                            description: 'Existing transformation',
                            transformationId: initialTransformationId,
                            previewData: {
                                tables: result.tables,
                                execution_time_ms: result.execution_time_ms,
                                row_counts: result.row_counts
                            }
                        }
                    }
                    return {
                        ...prev,
                        previewData: {
                            tables: result.tables,
                            execution_time_ms: result.execution_time_ms,
                            row_counts: result.row_counts
                        }
                    }
                })

                previewLoadedRef.current = true
            } catch (error) {
                console.error('❌ Failed to load initial preview:', error)
            } finally {
                setIsGenerating(false)
            }
        }

        loadPreview()
    }, [open, initialCode, initialTransformationId, primaryNode?.id, token])

    // Auto-scroll chat
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [chatMessages])

    console.log('primaryNode check:', primaryNode)
    if (!primaryNode) {
        console.error('❌ primaryNode is null/undefined, returning null')
        return null
    }
    console.log('✅ primaryNode exists, rendering dialog')

    // Handle send message - iterative generation
    const handleSendMessage = async (messageText?: string) => {
        const textToSend = messageText || inputValue.trim()
        if (!textToSend || isGenerating) return

        const userMessage: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'user',
            content: textToSend,
            timestamp: new Date()
        }

        setChatMessages(prev => [...prev, userMessage])
        setInputValue('')
        setIsGenerating(true)

        try {
            // Build chat history
            const fullChatHistory = [
                ...chatMessages.map(msg => ({
                    role: msg.role,
                    content: msg.content
                })),
                { role: userMessage.role, content: userMessage.content }
            ]

            // Call iterative transform endpoint
            const headers: Record<string, string> = { 'Content-Type': 'application/json' }
            if (token) {
                headers['Authorization'] = `Bearer ${token}`
            }

            const response = await fetch(`/api/v1/content-nodes/${primaryNode.id}/transform/iterative`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    user_prompt: userMessage.content,
                    existing_code: currentTransformation?.code,
                    transformation_id: currentTransformation?.transformationId,
                    chat_history: fullChatHistory,
                    selected_node_ids: nodes.map(n => n.id),
                    preview_only: true
                }),
                credentials: 'include'
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Ошибка генерации')
            }

            const data = await response.json()

            console.log('🤖 AI response received:', data)

            // Check if execution failed
            const executionError = !data.preview_data
                ? `Код не выполнился. ${data.validation?.errors?.[0] || 'Проверьте синтаксис.'}`
                : undefined

            // Add AI response
            const aiMessage: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: data.description || 'Трансформация создана',
                timestamp: new Date()
            }
            setChatMessages(prev => [...prev, aiMessage])

            // Update transformation state
            setCurrentTransformation({
                code: data.code,
                description: data.description,
                transformationId: data.transformation_id,
                previewData: data.preview_data,
                error: executionError
            })

            if (executionError) {
                console.error('❌ Execution failed:', executionError)
            }

            // Reset edited code
            setEditedCode(null)

            // Switch to preview tab to show results
            setRightPanelTab('preview')

        } catch (error) {
            console.error('Transform generation failed:', error)
            const errorMessage: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: `❌ ${error instanceof Error ? error.message : 'Ошибка генерации кода'}`,
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
        const textarea = e.target
        textarea.style.height = 'auto'
        textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`
    }

    // Apply manual code edits
    const handleApplyCode = async () => {
        if (!editedCode || !currentTransformation) return

        setIsGenerating(true)
        try {
            // Test edited code
            const headers: Record<string, string> = { 'Content-Type': 'application/json' }
            if (token) {
                headers['Authorization'] = `Bearer ${token}`
            }

            const response = await fetch(`/api/v1/content-nodes/${primaryNode.id}/transform/test`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    code: editedCode,
                    transformation_id: currentTransformation.transformationId,
                    selected_node_ids: nodes.map(n => n.id)
                }),
                credentials: 'include'
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Ошибка выполнения кода')
            }

            const result = await response.json()

            // Update transformation with tested code
            setCurrentTransformation({
                ...currentTransformation,
                code: editedCode,
                previewData: {
                    tables: result.tables,
                    execution_time_ms: result.execution_time_ms
                }
            })

            setEditedCode(null)
            setRightPanelTab('preview')
        } catch (error) {
            console.error('Code test failed:', error)
            alert(`Ошибка: ${error instanceof Error ? error.message : 'Не удалось выполнить код'}`)
        } finally {
            setIsGenerating(false)
        }
    }

    // Save transformation
    const handleSaveToBoard = async () => {
        if (!currentTransformation || isSaving) return

        setIsSaving(true)
        try {
            const code = editedCode || currentTransformation.code
            await onTransform(code, currentTransformation.transformationId, currentTransformation.description)
            onOpenChange(false)
        } catch (error) {
            console.error('Failed to save transformation:', error)
            alert(`Ошибка: ${error instanceof Error ? error.message : 'Не удалось сохранить'}`)
        } finally {
            setIsSaving(false)
        }
    }

    // Render table helper
    const renderTable = (table: PreviewData['tables'][0]) => (
        <div className="border rounded-lg p-3 space-y-3">
            <div className="flex items-center justify-between">
                <div className="font-medium">
                    Таблица: <code className="bg-primary/10 px-1.5 py-0.5 rounded text-sm">{table.name}</code>
                </div>
                <div className="text-xs text-muted-foreground">
                    {table.preview_row_count < table.row_count ? (
                        <span>Показано {table.preview_row_count} из {table.row_count} строк</span>
                    ) : (
                        <span>{table.row_count} строк</span>
                    )}
                </div>
            </div>
            <div className="border rounded overflow-x-auto max-h-[300px] overflow-y-auto">
                <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-muted">
                        <tr className="border-b">
                            {table.columns.map((col, idx) => {
                                // Handle both old (string) and new (object) column formats
                                const colName = typeof col === 'string' ? col : col.name || String(col)
                                return (
                                    <th key={`col-${colName}-${idx}`} className="px-2 py-1.5 text-left font-medium">
                                        {colName}
                                    </th>
                                )
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {table.rows.map((row, rowIdx) => {
                            // Handle both old (array) and new (object) row formats
                            const rowValues = Array.isArray(row) ? row : row.values || []
                            return (
                                <tr key={`row-${rowIdx}`} className="border-b last:border-0 hover:bg-muted/50">
                                    {rowValues.map((cell, cellIdx) => (
                                        <td key={`cell-${rowIdx}-${cellIdx}`} className="px-2 py-1.5">
                                            {cell !== null && cell !== undefined ? String(cell) : '-'}
                                        </td>
                                    ))}
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    )

    // Render source table helper
    const renderSourceTable = (table: ContentNode['content']['tables'][0], index: number) => (
        <div className="border rounded p-2 space-y-2">
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
                                    <th key={`stat-col-${colName}-${idx}`} className="px-1 py-0.5 text-left font-medium">
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
                                <tr key={`stat-row-${rowIdx}`} className="border-t">
                                    {rowValues.slice(0, 4).map((cell, cellIdx) => (
                                        <td key={`stat-cell-${rowIdx}-${cellIdx}`} className="px-1 py-0.5">
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
            <DialogContent className="max-w-[1400px] h-[90vh] p-0 flex flex-col nodrag nopan">
                <DialogHeader className="px-6 py-1.5 border-b shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-sm leading-tight">
                        <Code className="h-3.5 w-3.5 text-blue-500" />
                        AI-ассистент трансформаций
                    </DialogTitle>
                    <DialogDescription className="text-xs leading-tight mt-0.5">
                        Создайте трансформацию с помощью AI или отредактируйте код вручную
                    </DialogDescription>
                </DialogHeader>

                <div className="flex flex-1 min-h-0">
                    {/* Left Panel (40%) - Data + Chat */}
                    <div className="w-[40%] border-r flex flex-col">
                        {/* Source Data Preview */}
                        <div className="flex-1 p-2 border-b overflow-y-auto max-h-[45%]">
                            <div className="text-xs font-medium mb-2">📊 Исходные данные:</div>
                            {allTables.length > 0 ? (
                                <Tabs value={selectedSourceTableIndex.toString()} onValueChange={(v) => setSelectedSourceTableIndex(Number(v))}>
                                    <TabsList className="grid w-full h-7" style={{ gridTemplateColumns: `repeat(${Math.min(allTables.length, 3)}, 1fr)` }}>
                                        {allTables.slice(0, 3).map((table, idx) => (
                                            <TabsTrigger key={`${table.name}-${idx}`} value={idx.toString()} className="text-xs h-6 py-0">
                                                {table.name} ({table.row_count})
                                            </TabsTrigger>
                                        ))}
                                    </TabsList>
                                    <TabsContent value={selectedSourceTableIndex.toString()} className="mt-1">
                                        {renderSourceTable(allTables[selectedSourceTableIndex], selectedSourceTableIndex)}
                                    </TabsContent>
                                </Tabs>
                            ) : (
                                <div className="text-xs text-muted-foreground">Нет данных</div>
                            )}
                        </div>

                        {/* Chat Messages */}
                        <div className="flex items-center justify-between px-3 pt-2 pb-1">
                            <span className="text-xs font-medium text-muted-foreground">💬 Диалог с AI</span>
                            {chatMessages.length > 0 && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 px-2 text-xs text-muted-foreground hover:text-destructive"
                                    onClick={() => {
                                        setChatMessages([])
                                        setCurrentTransformation(null)
                                        setEditedCode(null)
                                    }}
                                >
                                    <Trash2 className="w-3 h-3 mr-1" />
                                    Очистить
                                </Button>
                            )}
                        </div>
                        <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-2">
                            {chatMessages.length === 0 ? (
                                <div key="empty-placeholder" className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                                    <Sparkles className="w-10 h-10 mb-3 text-blue-500/30" />
                                    <p className="text-sm">
                                        Опишите какую трансформацию выполнить
                                    </p>
                                    <p className="text-xs mt-2">
                                        Например: "Отфильтровать amount &gt; 100"
                                    </p>
                                </div>
                            ) : (
                                <div key="messages-container" className="space-y-2">
                                    {chatMessages.map((msg) => (
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
                                                        ? 'bg-blue-500 text-white'
                                                        : 'bg-muted'
                                                )}
                                            >
                                                {msg.content}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                            {isGenerating && (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    AI создаёт код трансформации...
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Suggestions Panel */}
                        <div className="border-t overflow-y-auto max-h-[120px]">
                            <TransformSuggestionsPanel
                                contentNodeId={primaryNode.id}
                                chatHistory={chatMessages.map(msg => ({
                                    role: msg.role,
                                    content: msg.content
                                }))}
                                currentCode={currentTransformation?.code}
                                onSuggestionClick={handleSendMessage}
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
                                    placeholder="Опишите трансформацию..."
                                    className="min-h-[32px] py-1.5 px-2 resize-none text-sm overflow-hidden"
                                    style={{ height: '32px' }}
                                    disabled={isGenerating}
                                    rows={1}
                                />
                                <Button
                                    onClick={() => handleSendMessage()}
                                    disabled={!inputValue.trim() || isGenerating}
                                    size="icon"
                                    className="h-[32px] w-[32px] shrink-0 bg-blue-500 hover:bg-blue-600"
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

                    {/* Right Panel (60%) - Preview & Code */}
                    <div className="w-[60%] flex flex-col">
                        {/* Tabs */}
                        <div className="px-3 pt-2 pb-1 border-b">
                            {currentTransformation?.transformationId && (
                                <div className="text-xs text-muted-foreground mb-1.5">
                                    ID: {currentTransformation.transformationId.slice(0, 8)}...
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
                                        Код Python/pandas
                                    </TabsTrigger>
                                </TabsList>
                            </Tabs>
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 p-3 flex flex-col overflow-hidden">
                            {/* Preview Panel */}
                            <div className={cn("flex-1 flex flex-col overflow-hidden", rightPanelTab !== 'preview' && "hidden")}>
                                {currentTransformation?.error ? (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="text-center max-w-md">
                                            <div className="text-destructive text-sm font-medium mb-2">
                                                ❌ Ошибка выполнения
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                {currentTransformation.error}
                                            </div>
                                            <div className="text-xs text-muted-foreground mt-2">
                                                Проверьте код во вкладке "Код Python/pandas"
                                            </div>
                                        </div>
                                    </div>
                                ) : currentTransformation?.previewData ? (
                                    <div className="flex-1 flex flex-col overflow-hidden">
                                        <div className="text-xs text-muted-foreground mb-2">
                                            ⚡ Выполнено за {currentTransformation.previewData?.execution_time_ms || 0}ms
                                        </div>

                                        {/* Tabs for multiple tables */}
                                        {(currentTransformation.previewData?.tables?.length || 0) > 1 ? (
                                            <Tabs defaultValue="0" className="flex-1 flex flex-col overflow-hidden">
                                                <TabsList className="h-8 shrink-0">
                                                    {currentTransformation.previewData?.tables?.map((table, idx) => (
                                                        <TabsTrigger
                                                            key={`preview-tab-${table.name}-${idx}`}
                                                            value={String(idx)}
                                                            className="text-xs h-7 px-2"
                                                        >
                                                            {table.name} <span className="ml-1 text-muted-foreground">({table.row_count})</span>
                                                        </TabsTrigger>
                                                    ))}
                                                </TabsList>
                                                {currentTransformation.previewData?.tables?.map((table, idx) => (
                                                    <TabsContent
                                                        key={`preview-content-${table.name}-${idx}`}
                                                        value={String(idx)}
                                                        className="flex-1 mt-2 overflow-hidden"
                                                    >
                                                        <div className="h-full overflow-y-auto">
                                                            {renderTable(table)}
                                                        </div>
                                                    </TabsContent>
                                                ))}
                                            </Tabs>
                                        ) : currentTransformation.previewData?.tables?.[0] ? (
                                            <div className="flex-1 overflow-y-auto">
                                                {renderTable(currentTransformation.previewData.tables[0])}
                                            </div>
                                        ) : null}
                                    </div>
                                ) : (
                                    <div className="flex-1 flex items-center justify-center text-muted-foreground">
                                        <div className="text-center">
                                            <Eye className="w-12 h-12 mx-auto mb-2 opacity-30" />
                                            <p className="text-sm">Результаты появятся после генерации</p>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Code Panel */}
                            <div className={cn("flex-1 flex flex-col", rightPanelTab !== 'code' && "hidden")}>
                                {editedCode && (
                                    <div className="flex items-center justify-end mb-2">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={handleApplyCode}
                                            disabled={isGenerating}
                                        >
                                            {isGenerating ? (
                                                <><Loader2 className="w-3 h-3 mr-1 animate-spin" />Тестирование...</>
                                            ) : (
                                                <>Применить изменения</>
                                            )}
                                        </Button>
                                    </div>
                                )}
                                {currentTransformation ? (
                                    <div className="flex-1 flex flex-col overflow-hidden">
                                        <div className="text-xs font-medium mb-2">Python/pandas код</div>
                                        <div className="flex-1 border rounded-lg overflow-hidden">
                                            <Editor
                                                height="100%"
                                                language="python"
                                                value={editedCode || currentTransformation.code}
                                                onChange={(value) => setEditedCode(value || null)}
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
                                            <p className="text-sm">Код появится после генерации</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                <DialogFooter className="px-6 py-1.5 border-t shrink-0">
                    <div className="flex items-center justify-between w-full">
                        <div className="text-xs text-muted-foreground">
                            {currentTransformation && (
                                <>📝 {currentTransformation.description}</>
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
                                disabled={!currentTransformation || isSaving}
                                className="bg-blue-500 hover:bg-blue-600"
                            >
                                {isSaving ? (
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <Save className="w-4 h-4 mr-2" />
                                )}
                                {isSaving ? 'Сохранение...' : 'Сохранить трансформацию'}
                            </Button>
                        </div>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
