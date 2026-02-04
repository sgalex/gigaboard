import { useState } from 'react'
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
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Code, Loader2, Sparkles, AlertCircle, Play, Eye, Edit3, CheckCircle, Clock } from 'lucide-react'
import { ContentNode } from '@/types'
import { useAuthStore } from '@/store/authStore'

interface TransformDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    sourceNode?: ContentNode  // Backward compatible: single node
    sourceNodes?: ContentNode[]  // Multi-node support
    onTransform: (prompt: string, code?: string, transformationId?: string) => Promise<void>
    // Optional: pre-fill dialog with existing transformation
    initialCode?: string
    initialPrompt?: string
    initialTransformationId?: string
}

type Step = 'prompt' | 'preview' | 'result'

interface PreviewResult {
    transformation_id: string
    code: string
    description: string
    validation: {
        valid: boolean
        errors: string[]
        warnings: any[]
        suggestions: string[]
    }
    agent_plan: {
        steps: string[]
        attempts: number
        total_time_ms: number
    }
    analysis: any
}

interface TestResult {
    success: boolean
    tables: Array<{
        name: string
        columns: string[]
        rows: Array<Array<any>>
        row_count: number
        preview_row_count: number
    }>
    execution_time_ms: number
    row_counts: Record<string, number>
    error?: string
}

export function TransformDialog({
    open,
    onOpenChange,
    sourceNode,
    sourceNodes,
    onTransform,
    initialCode,
    initialPrompt,
    initialTransformationId,
}: TransformDialogProps) {
    // Normalize to array (backward compatible with single node)
    const nodes = sourceNodes || (sourceNode ? [sourceNode] : [])
    const primaryNode = nodes[0]

    if (!primaryNode) {
        return null  // No source nodes provided
    }

    const [step, setStep] = useState<Step>(initialCode ? 'preview' : 'prompt')
    const [prompt, setPrompt] = useState(initialPrompt || '')
    const [previewResult, setPreviewResult] = useState<PreviewResult | null>(
        initialCode ? {
            transformation_id: initialTransformationId || '',
            code: initialCode,
            description: initialPrompt || 'Existing transformation',
            validation: { valid: true, errors: [], warnings: [], suggestions: [] },
            agent_plan: { steps: [], attempts: 1, total_time_ms: 0 },
            analysis: {}
        } : null
    )
    const [testResult, setTestResult] = useState<TestResult | null>(null)
    const [editedCode, setEditedCode] = useState(initialCode || '')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const token = useAuthStore((state) => state.token)

    // Calculate total stats from all nodes
    const allTables = nodes.flatMap(n => n.content?.tables || [])
    const tableCount = allTables.length
    const totalRows = allTables.reduce((sum, t) => sum + (t.row_count || 0), 0)

    // Helper function to render a single table
    const renderTable = (table: TestResult['tables'][0]) => (
        <div className="border rounded-lg p-3 space-y-3">
            <div className="flex items-center justify-between">
                <div className="font-medium">
                    Таблица: <code className="bg-primary/10 px-1.5 py-0.5 rounded text-sm">{table.name}</code>
                </div>
                <div className="text-xs text-muted-foreground">
                    {table.row_count} {table.row_count === 1 ? 'строка' : table.row_count < 5 ? 'строки' : 'строк'}
                    {table.preview_row_count < table.row_count && (
                        <span> (показано первых {table.preview_row_count})</span>
                    )}
                </div>
            </div>

            {/* Table preview */}
            <div className="border rounded overflow-x-auto max-h-[300px] overflow-y-auto">
                <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-muted">
                        <tr className="border-b">
                            {table.columns.map((col, colIdx) => {
                                // Handle both old (string) and new (object) column formats
                                const colName = typeof col === 'string' ? col : col.name || String(col)
                                return (
                                    <th key={colIdx} className="px-2 py-1.5 text-left font-medium">
                                        {colName}
                                    </th>
                                )
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {table.rows.map((row: any, rowIdx: number) => {
                            // Handle both old (array) and new (object) row formats
                            const rowValues = Array.isArray(row) ? row : row.values || []
                            return (
                                <tr key={rowIdx} className="border-b last:border-0 hover:bg-muted/50">
                                    {rowValues.map((cell: any, cellIdx: number) => (
                                        <td key={cellIdx} className="px-2 py-1.5">
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

    const handleGenerateCode = async () => {
        if (!prompt.trim()) {
            setError('Пожалуйста, опишите трансформацию')
            return
        }

        setError(null)
        setIsLoading(true)

        try {
            // Call preview endpoint
            const headers: Record<string, string> = { 'Content-Type': 'application/json' }
            if (token) {
                headers['Authorization'] = `Bearer ${token}`
            }
            const response = await fetch(`/api/v1/content-nodes/${primaryNode.id}/transform/preview`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    prompt,
                    selected_node_ids: nodes.map(n => n.id)
                }),
                credentials: 'include'
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Ошибка генерации кода')
            }

            const result: PreviewResult = await response.json()

            // Check validation
            if (!result.validation.valid) {
                setError(`Ошибка валидации кода: ${result.validation.errors.join(', ')}`)
                return
            }

            setPreviewResult(result)
            setEditedCode(result.code)
            setStep('preview')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Ошибка генерации кода')
        } finally {
            setIsLoading(false)
        }
    }

    const handleTestCode = async () => {
        if (!previewResult) return

        setError(null)
        setIsLoading(true)

        try {
            const headers: Record<string, string> = { 'Content-Type': 'application/json' }
            if (token) {
                headers['Authorization'] = `Bearer ${token}`
            }
            const response = await fetch(`/api/v1/content-nodes/${primaryNode.id}/transform/test`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    code: editedCode,
                    transformation_id: previewResult.transformation_id,
                    selected_node_ids: nodes.map(n => n.id)
                }),
                credentials: 'include'
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Ошибка выполнения кода')
            }

            const result: TestResult = await response.json()

            if (!result.success) {
                setError(`Ошибка выполнения: ${result.error || 'Unknown error'}`)
                return
            }

            setTestResult(result)
            setStep('result')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Ошибка тестирования')
        } finally {
            setIsLoading(false)
        }
    }

    const handleExecuteCode = async () => {
        console.log('🎬 handleExecuteCode called', { previewResult, editedCode: editedCode?.substring(0, 100) })

        if (!previewResult) return

        setError(null)
        setIsLoading(true)

        try {
            console.log('📞 Calling onTransform...', { prompt, transformationId: previewResult.transformation_id })
            await onTransform(prompt, editedCode, previewResult.transformation_id)
            console.log('✅ onTransform completed')
            handleClose()
        } catch (err) {
            console.error('❌ onTransform failed:', err)
            setError(err instanceof Error ? err.message : 'Ошибка выполнения')
        } finally {
            setIsLoading(false)
        }
    }

    const handleClose = () => {
        setStep('prompt')
        setPrompt('')
        setPreviewResult(null)
        setTestResult(null)
        setEditedCode('')
        setError(null)
        onOpenChange(false)
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
                <DialogHeader className="flex-shrink-0">
                    <DialogTitle className="flex items-center gap-2">
                        <Code className="w-5 h-5" />
                        Трансформация данных
                        {step === 'preview' && <span className="text-sm font-normal text-muted-foreground ml-2">• Предпросмотр кода</span>}
                        {step === 'result' && <span className="text-sm font-normal text-muted-foreground ml-2">• Результаты</span>}
                    </DialogTitle>
                    <DialogDescription>
                        {step === 'prompt' && 'Опишите, как вы хотите преобразовать данные'}
                        {step === 'preview' && 'Проверьте и отредактируйте сгенерированный код перед выполнением'}
                        {step === 'result' && 'Результаты трансформации - проверьте перед созданием ноды'}
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto overflow-x-hidden py-4 px-1 min-h-0">
                    {step === 'prompt' && (
                        <div className="space-y-4">
                            {/* Source info */}
                            <div className="p-3 bg-muted rounded-lg text-sm space-y-2">
                                <div className="font-medium flex items-center gap-2 flex-wrap">
                                    <span>Исходные данные:</span>
                                    {nodes.map((node, nodeIdx) => (
                                        <span key={nodeIdx} className="inline-flex items-center gap-1.5 text-muted-foreground font-normal">
                                            <span className="text-xs">•</span>
                                            <span>{node.metadata?.name || `Content Node ${node.id.slice(0, 8)}`}</span>
                                        </span>
                                    ))}
                                    <span className="text-xs text-muted-foreground font-normal">
                                        ({tableCount} {tableCount === 1 ? 'таблица' : tableCount < 5 ? 'таблицы' : 'таблиц'}, {totalRows} {totalRows === 1 ? 'строка' : totalRows < 5 ? 'строки' : 'строк'})
                                    </span>
                                </div>
                                {allTables.length > 0 && (
                                    <Tabs defaultValue={allTables[0]?.name || 'table-0'} className="mt-3">
                                        <TabsList className="w-full justify-start overflow-x-auto flex-nowrap h-auto">
                                            {allTables.map((table, idx) => (
                                                <TabsTrigger
                                                    key={idx}
                                                    value={table.name || `table-${idx}`}
                                                    className="flex items-center gap-2"
                                                >
                                                    <span>{table.name}</span>
                                                    <span className="text-xs text-muted-foreground">
                                                        ({table.row_count || 0})
                                                    </span>
                                                </TabsTrigger>
                                            ))}
                                        </TabsList>

                                        {allTables.map((table, idx) => (
                                            <TabsContent key={idx} value={table.name || `table-${idx}`} className="mt-3">
                                                {/* Sample data preview */}
                                                {table.rows && table.rows.length > 0 && (
                                                    <div className="text-xs">
                                                        <span className="text-muted-foreground">Примеры данных (первые {Math.min(3, table.rows.length)} строки):</span>
                                                        <div className="mt-1 bg-background/50 rounded border overflow-x-auto">
                                                            <table className="w-full text-xs">
                                                                <thead>
                                                                    <tr className="border-b">
                                                                        {table.columns?.map((col, colIdx) => {
                                                                            // Handle both old (string) and new (object) column formats
                                                                            const colName = typeof col === 'string' ? col : col.name || String(col)
                                                                            return (
                                                                                <th key={colIdx} className="px-2 py-1 text-left font-medium text-muted-foreground">
                                                                                    {colName}
                                                                                </th>
                                                                            )
                                                                        })}
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    {table.rows.slice(0, 3).map((row: any, rowIdx: number) => (
                                                                        <tr key={rowIdx} className="border-b last:border-0">
                                                                            {Array.isArray(row) ? row.map((cell: any, cellIdx: number) => (
                                                                                <td key={cellIdx} className="px-2 py-1">
                                                                                    {cell !== null && cell !== undefined ? String(cell) : '-'}
                                                                                </td>
                                                                            )) : null}
                                                                        </tr>
                                                                    ))}
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                )}
                                            </TabsContent>
                                        ))}
                                    </Tabs>
                                )}
                            </div>

                            {/* Transformation prompt */}
                            <div className="space-y-2">
                                <Label htmlFor="transform-prompt">
                                    Опишите трансформацию
                                </Label>
                                <Textarea
                                    id="transform-prompt"
                                    placeholder="Например: Отфильтровать строки где amount > 100 и сгруппировать по region, подсчитав сумму revenue"
                                    value={prompt}
                                    onChange={(e) => setPrompt(e.target.value)}
                                    rows={5}
                                    className="resize-none"
                                />
                                <p className="text-xs text-muted-foreground">
                                    AI-агенты проанализируют ваши данные и сгенерируют Python/pandas код
                                </p>
                            </div>

                            {/* Examples */}
                            <div className="space-y-2">
                                <div className="text-sm font-medium">Примеры трансформаций:</div>
                                <div className="space-y-1 text-xs text-muted-foreground">
                                    <div>• "Посчитать общую выручку по категориям товаров"</div>
                                    <div>• "Отфильтровать строки где дата в 2026 году и amount &gt; 1000"</div>
                                    <div>• "Сгруппировать по месяцам и посчитать средние значения"</div>
                                    <div>• "Добавить новую колонку с процентом от общей суммы"</div>
                                </div>
                            </div>
                        </div>
                    )}

                    {step === 'preview' && previewResult && (
                        <div className="space-y-4">
                            {/* Agent plan info */}
                            <div className="p-3 bg-muted rounded-lg text-sm space-y-2">
                                <div className="flex items-center gap-2">
                                    <CheckCircle className="w-4 h-4 text-green-600" />
                                    <span className="font-medium">Multi-Agent генерация завершена</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 text-xs text-muted-foreground">
                                    <div>
                                        <div className="font-medium text-foreground">Использованные агенты:</div>
                                        {previewResult.agent_plan.steps.map((step, idx) => (
                                            <div key={idx}>• {step}</div>
                                        ))}
                                    </div>
                                    <div>
                                        <div className="font-medium text-foreground">Попытки:</div>
                                        {previewResult.agent_plan.attempts}
                                    </div>
                                    <div>
                                        <div className="font-medium text-foreground">Время:</div>
                                        <Clock className="inline w-3 h-3 mr-1" />
                                        {previewResult.agent_plan.total_time_ms}мс
                                    </div>
                                </div>
                            </div>

                            {/* Validation status */}
                            {previewResult.validation.warnings.length > 0 && (
                                <Alert>
                                    <AlertCircle className="h-4 w-4" />
                                    <AlertDescription>
                                        <div className="font-medium mb-1">Предупреждения:</div>
                                        {previewResult.validation.warnings.map((w, idx) => (
                                            <div key={idx} className="text-xs">• {w.message}</div>
                                        ))}
                                    </AlertDescription>
                                </Alert>
                            )}

                            {/* Code editor */}
                            <Tabs defaultValue="code" className="w-full">
                                <TabsList className="grid w-full grid-cols-2">
                                    <TabsTrigger value="code">
                                        <Code className="w-4 h-4 mr-2" />
                                        Сгенерированный код
                                    </TabsTrigger>
                                    <TabsTrigger value="info">
                                        <Eye className="w-4 h-4 mr-2" />
                                        Анализ
                                    </TabsTrigger>
                                </TabsList>
                                <TabsContent value="code" className="mt-4">
                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between">
                                            <Label className="flex items-center gap-2">
                                                <Edit3 className="w-4 h-4" />
                                                Редактировать код перед выполнением
                                            </Label>
                                            <span className="text-xs text-muted-foreground">
                                                Python • pandas
                                            </span>
                                        </div>
                                        <div className="border rounded-md overflow-hidden">
                                            <Editor
                                                height="300px"
                                                defaultLanguage="python"
                                                value={editedCode}
                                                onChange={(value) => setEditedCode(value || '')}
                                                theme="vs-dark"
                                                options={{
                                                    minimap: { enabled: false },
                                                    fontSize: 13,
                                                    lineNumbers: 'on',
                                                    scrollBeyondLastLine: false,
                                                    automaticLayout: true,
                                                }}
                                            />
                                        </div>
                                        <p className="text-xs text-muted-foreground">
                                            💡 Вы можете отредактировать код перед запуском. Изменения будут проверены при выполнении.
                                        </p>
                                    </div>
                                </TabsContent>
                                <TabsContent value="info" className="mt-4 space-y-3">
                                    <div className="p-3 bg-muted rounded-lg text-sm">
                                        <div className="font-medium mb-1">Описание:</div>
                                        <div className="text-muted-foreground">{previewResult.description}</div>
                                    </div>
                                    {previewResult.analysis && (
                                        <div className="p-3 bg-muted rounded-lg text-sm">
                                            <div className="font-medium mb-2">Анализ данных:</div>
                                            <div className="space-y-1 text-xs text-muted-foreground">
                                                {previewResult.analysis.column_types && (
                                                    <div>
                                                        <span className="font-medium text-foreground">Типы колонок:</span>
                                                        <div className="mt-1">
                                                            {Object.entries(previewResult.analysis.column_types).map(([col, type]) => (
                                                                <div key={col}>• {col}: {type as string}</div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                                {previewResult.analysis.recommendations && (
                                                    <div className="mt-2">
                                                        <span className="font-medium text-foreground">Рекомендации:</span>
                                                        <div className="mt-1">{previewResult.analysis.recommendations}</div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </TabsContent>
                            </Tabs>
                        </div>
                    )}

                    {/* Result step */}
                    {step === 'result' && testResult && (
                        <div className="space-y-4">
                            {/* Execution info */}
                            <div className="p-3 bg-muted rounded-lg text-sm flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <CheckCircle className="w-4 h-4 text-green-500" />
                                    <span className="font-medium">Трансформация выполнена успешно</span>
                                </div>
                                <div className="flex items-center gap-2 text-muted-foreground">
                                    <Clock className="w-4 h-4" />
                                    <span>{testResult.execution_time_ms}ms</span>
                                </div>
                            </div>

                            {/* Result tables */}
                            {testResult.tables.length === 1 ? (
                                // Single table - no tabs needed
                                <div className="space-y-4">
                                    <div className="font-medium text-sm">Результирующая таблица:</div>
                                    {renderTable(testResult.tables[0])}
                                </div>
                            ) : (
                                // Multiple tables - use tabs
                                <div className="space-y-2">
                                    <div className="font-medium text-sm">Результирующие таблицы ({testResult.tables.length}):</div>
                                    <Tabs defaultValue="0" className="w-full">
                                        <TabsList className="grid w-full" style={{ gridTemplateColumns: `repeat(${testResult.tables.length}, 1fr)` }}>
                                            {testResult.tables.map((table, idx) => (
                                                <TabsTrigger key={idx} value={String(idx)} className="text-xs">
                                                    {table.name}
                                                    <span className="ml-1.5 text-muted-foreground">({table.row_count})</span>
                                                </TabsTrigger>
                                            ))}
                                        </TabsList>
                                        {testResult.tables.map((table, idx) => (
                                            <TabsContent key={idx} value={String(idx)} className="mt-3">
                                                {renderTable(table)}
                                            </TabsContent>
                                        ))}
                                    </Tabs>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Error */}
                    {error && (
                        <Alert variant="destructive" className="mt-4">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}
                </div>

                <DialogFooter className="flex-shrink-0 border-t pt-4">
                    {step === 'prompt' && (
                        <>
                            <Button
                                variant="outline"
                                onClick={handleClose}
                                disabled={isLoading}
                            >
                                Отмена
                            </Button>
                            <Button
                                onClick={handleGenerateCode}
                                disabled={isLoading || !prompt.trim()}
                            >
                                {isLoading ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Генерация кода...
                                    </>
                                ) : (
                                    <>
                                        <Sparkles className="mr-2 h-4 w-4" />
                                        Сгенерировать код
                                    </>
                                )}
                            </Button>
                        </>
                    )}

                    {step === 'preview' && (
                        <>
                            <Button
                                variant="outline"
                                onClick={() => setStep('prompt')}
                                disabled={isLoading}
                            >
                                Назад
                            </Button>
                            <Button
                                onClick={handleTestCode}
                                disabled={isLoading}
                                variant="default"
                            >
                                {isLoading ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Выполнение...
                                    </>
                                ) : (
                                    <>
                                        <Eye className="mr-2 h-4 w-4" />
                                        Выполнить и посмотреть результат
                                    </>
                                )}
                            </Button>
                        </>
                    )}

                    {step === 'result' && (
                        <>
                            <Button
                                variant="outline"
                                onClick={() => setStep('preview')}
                                disabled={isLoading}
                            >
                                Назад к коду
                            </Button>
                            <Button
                                onClick={handleExecuteCode}
                                disabled={isLoading}
                            >
                                {isLoading ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Создание...
                                    </>
                                ) : (
                                    <>
                                        <CheckCircle className="mr-2 h-4 w-4" />
                                        Создать ноду с этими данными
                                    </>
                                )}
                            </Button>
                        </>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
