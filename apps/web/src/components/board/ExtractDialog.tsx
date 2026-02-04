import { useState, useRef, useEffect } from 'react'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
    Play,
    Loader2,
    FileText,
    Database,
    Globe,
    MessageSquare,
    Radio,
    Edit3,
    CheckCircle,
    AlertCircle,
    Info
} from 'lucide-react'
import { SourceNode, SourceType, ContentNode } from '@/types'
import { cn } from '@/lib/utils'

interface ExtractDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    sourceNode: SourceNode
    onExtract: (params?: Record<string, any>) => Promise<ContentNode | null>
}

// Icon mapping for source types
const sourceTypeIcons: Record<SourceType, React.ComponentType<{ className?: string }>> = {
    [SourceType.FILE]: FileText,
    [SourceType.DATABASE]: Database,
    [SourceType.API]: Globe,
    [SourceType.PROMPT]: MessageSquare,
    [SourceType.STREAM]: Radio,
    [SourceType.MANUAL]: Edit3,
}

// Source type descriptions
const sourceTypeDescriptions: Record<SourceType, string> = {
    [SourceType.FILE]: 'Извлечение данных из файла (CSV, JSON, Excel, Parquet, TXT)',
    [SourceType.DATABASE]: 'Выполнение SQL запроса к базе данных',
    [SourceType.API]: 'Получение данных из REST API endpoint',
    [SourceType.PROMPT]: 'Генерация данных через AI на основе текстового запроса',
    [SourceType.STREAM]: 'Подключение к потоку данных (WebSocket, SSE)',
    [SourceType.MANUAL]: 'Использование вручную введённых данных',
}

export function ExtractDialog({
    open,
    onOpenChange,
    sourceNode,
    onExtract,
}: ExtractDialogProps) {
    const [isExtracting, setIsExtracting] = useState(false)
    const [previewRows, setPreviewRows] = useState<number>(100)
    const [validationStatus, setValidationStatus] = useState<'idle' | 'validating' | 'valid' | 'invalid'>('idle')
    const [validationErrors, setValidationErrors] = useState<string[]>([])
    const [activeTab, setActiveTab] = useState<'config' | 'params'>('config')

    const Icon = sourceTypeIcons[sourceNode.source_type]

    // Reset state when dialog opens
    useEffect(() => {
        if (open) {
            setValidationStatus('idle')
            setValidationErrors([])
            setActiveTab('config')
        }
    }, [open])

    // Get config summary based on source type
    const getConfigSummary = (): string => {
        const config = sourceNode.config

        switch (sourceNode.source_type) {
            case SourceType.FILE:
                return config.filename || config.file_path || 'Файл не указан'
            case SourceType.DATABASE:
                return `${config.database_type || 'Database'}: ${config.query?.substring(0, 50) || 'No query'}...`
            case SourceType.API:
                return `${config.method || 'GET'} ${config.url || 'No URL'}`
            case SourceType.PROMPT:
                return config.prompt?.substring(0, 80) + '...' || 'Промпт не указан'
            case SourceType.STREAM:
                return `${config.stream_type || 'Stream'}: ${config.stream_url || 'No URL'}`
            case SourceType.MANUAL:
                return `${config.format || 'unknown'} format`
            default:
                return 'Неизвестный источник'
        }
    }

    const handleExtract = async () => {
        setIsExtracting(true)
        try {
            const params: Record<string, any> = {}

            // Add preview_rows for file and database sources
            if ([SourceType.FILE, SourceType.DATABASE].includes(sourceNode.source_type)) {
                if (previewRows > 0) {
                    params.preview_rows = previewRows
                }
            }

            await onExtract(params)
            onOpenChange(false)
        } catch (error) {
            console.error('Extraction failed:', error)
        } finally {
            setIsExtracting(false)
        }
    }

    const getParamsHelp = (): string => {
        switch (sourceNode.source_type) {
            case SourceType.FILE:
                return 'Ограничьте количество строк для предварительного просмотра больших файлов'
            case SourceType.DATABASE:
                return 'Ограничьте количество строк результата (добавится LIMIT к запросу)'
            case SourceType.API:
                return 'Дополнительные параметры будут переданы в запрос'
            case SourceType.PROMPT:
                return 'AI сгенерирует данные на основе промпта из конфигурации'
            case SourceType.STREAM:
                return 'Будет создано подключение к потоку данных (функциональность в разработке)'
            case SourceType.MANUAL:
                return 'Данные уже введены вручную, будут использованы как есть'
            default:
                return ''
        }
    }

    const supportsPreviewRows = [SourceType.FILE, SourceType.DATABASE].includes(sourceNode.source_type)

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <div className="p-2 rounded-md bg-primary/10 text-primary">
                            <Icon className="w-5 h-5" />
                        </div>
                        Извлечение данных
                    </DialogTitle>
                    <DialogDescription>
                        {sourceTypeDescriptions[sourceNode.source_type]}
                    </DialogDescription>
                </DialogHeader>

                <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="flex-1 overflow-hidden flex flex-col">
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="config">
                            <Info className="mr-2 h-4 w-4" />
                            Конфигурация
                        </TabsTrigger>
                        <TabsTrigger value="params">
                            <Edit3 className="mr-2 h-4 w-4" />
                            Параметры
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="config" className="flex-1 overflow-y-auto space-y-4 mt-4">
                        {/* Source info */}
                        <div className="space-y-3">
                            <div>
                                <Label className="text-sm font-medium">Название источника</Label>
                                <div className="text-sm text-muted-foreground mt-1">
                                    {sourceNode.metadata?.name || 'Без названия'}
                                </div>
                            </div>

                            <div>
                                <Label className="text-sm font-medium">Тип источника</Label>
                                <div className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
                                    <Icon className="w-4 h-4" />
                                    {sourceNode.source_type}
                                </div>
                            </div>

                            <div>
                                <Label className="text-sm font-medium">Конфигурация</Label>
                                <div className="text-sm text-muted-foreground mt-1 font-mono bg-muted p-3 rounded-md">
                                    {getConfigSummary()}
                                </div>
                            </div>

                            {sourceNode.metadata?.description && (
                                <div>
                                    <Label className="text-sm font-medium">Описание</Label>
                                    <div className="text-sm text-muted-foreground mt-1">
                                        {sourceNode.metadata.description}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Validation status */}
                        {validationStatus === 'valid' && (
                            <Alert>
                                <CheckCircle className="h-4 w-4" />
                                <AlertDescription>
                                    Конфигурация источника валидна и готова к извлечению
                                </AlertDescription>
                            </Alert>
                        )}

                        {validationStatus === 'invalid' && (
                            <Alert variant="destructive">
                                <AlertCircle className="h-4 w-4" />
                                <AlertDescription>
                                    <div className="font-medium mb-1">Ошибки конфигурации:</div>
                                    <ul className="list-disc list-inside text-sm">
                                        {validationErrors.map((error, idx) => (
                                            <li key={idx}>{error}</li>
                                        ))}
                                    </ul>
                                </AlertDescription>
                            </Alert>
                        )}
                    </TabsContent>

                    <TabsContent value="params" className="flex-1 overflow-y-auto space-y-4 mt-4">
                        <Alert>
                            <Info className="h-4 w-4" />
                            <AlertDescription>
                                {getParamsHelp()}
                            </AlertDescription>
                        </Alert>

                        {supportsPreviewRows && (
                            <div className="space-y-2">
                                <Label htmlFor="preview-rows">
                                    Количество строк для предпросмотра
                                </Label>
                                <Input
                                    id="preview-rows"
                                    type="number"
                                    min={0}
                                    max={10000}
                                    value={previewRows}
                                    onChange={(e) => setPreviewRows(parseInt(e.target.value) || 0)}
                                    placeholder="100"
                                />
                                <p className="text-xs text-muted-foreground">
                                    Оставьте 0 для загрузки всех данных. Рекомендуется не более 1000 строк для больших датасетов.
                                </p>
                            </div>
                        )}

                        {sourceNode.source_type === SourceType.PROMPT && (
                            <Alert>
                                <MessageSquare className="h-4 w-4" />
                                <AlertDescription>
                                    <div className="font-medium mb-1">AI-генерация данных</div>
                                    <div className="text-sm">
                                        GigaChat сгенерирует данные на основе промпта:
                                        <div className="mt-2 font-mono text-xs bg-muted p-2 rounded">
                                            {sourceNode.config.prompt?.substring(0, 150)}...
                                        </div>
                                    </div>
                                </AlertDescription>
                            </Alert>
                        )}

                        {sourceNode.source_type === SourceType.STREAM && (
                            <Alert>
                                <Radio className="h-4 w-4" />
                                <AlertDescription>
                                    <div className="font-medium mb-1">Потоковые данные</div>
                                    <div className="text-sm">
                                        Функциональность потоковых данных находится в разработке (Phase 4).
                                        Сейчас будет возвращён placeholder.
                                    </div>
                                </AlertDescription>
                            </Alert>
                        )}
                    </TabsContent>
                </Tabs>

                <DialogFooter className="flex gap-2">
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        disabled={isExtracting}
                    >
                        Отмена
                    </Button>
                    <Button
                        onClick={handleExtract}
                        disabled={isExtracting}
                    >
                        {isExtracting ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Извлечение...
                            </>
                        ) : (
                            <>
                                <Play className="mr-2 h-4 w-4" />
                                Извлечь данные
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
