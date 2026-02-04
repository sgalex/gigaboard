import { useState } from 'react'
import { useBoardStore } from '@/store/boardStore'
import { useUIStore } from '@/store/uiStore'
import { DataSourceType } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { findFreePosition } from '@/lib/canvasUtils'
import { notify } from '@/store/notificationStore'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import {
    FileUp,
    Globe,
    FileText,
    FileJson,
    FileSpreadsheet,
} from 'lucide-react'

// Supported file types
type FileType = 'text' | 'csv' | 'json' | 'pdf' | 'docx' | 'xlsx' | 'unknown'

const FILE_ICONS: Record<FileType, typeof FileText> = {
    text: FileText,
    csv: FileSpreadsheet,
    json: FileJson,
    pdf: FileText,
    docx: FileText,
    xlsx: FileSpreadsheet,
    unknown: FileUp,
}

const FILE_EXTENSIONS: Record<string, FileType> = {
    'txt': 'text',
    'csv': 'csv',
    'json': 'json',
    'pdf': 'pdf',
    'docx': 'docx',
    'doc': 'docx',
    'xlsx': 'xlsx',
    'xls': 'xlsx',
}

// Simple mode types
type SimpleSourceMode = 'text' | 'file' | 'api'

// Mode configuration
const sourceModes = {
    text: {
        icon: FileText,
        label: 'Текст / Промпт',
        description: 'Задача для AI или произвольный текстовый контент',
    },
    file: {
        icon: FileUp,
        label: 'Файл',
        description: 'Загрузите файл любого формата - AI распознает структуру',
    },
    api: {
        icon: Globe,
        label: 'API',
        description: 'Получение данных через HTTP/REST API',
    },
}

export function CreateDataNodeDialog() {
    const { createDataNode, isLoading, dataNodes } = useBoardStore()
    const {
        isCreateDataNodeDialogOpen,
        closeCreateDataNodeDialog,
        contextBoardId,
        canvasCenter
    } = useUIStore()

    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [sourceMode, setSourceMode] = useState<SimpleSourceMode>('text')

    // API-specific fields
    const [apiEndpoint, setApiEndpoint] = useState('')
    const [apiMethod, setApiMethod] = useState('GET')
    const [apiHeaders, setApiHeaders] = useState('{}')
    const [apiBody, setApiBody] = useState('')

    // File upload-specific fields
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [fileContent, setFileContent] = useState('')
    const [fileType, setFileType] = useState<FileType>('unknown')
    const [filePreviewError, setFilePreviewError] = useState<string>('')

    // Text input
    const [textContent, setTextContent] = useState('')

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        setSelectedFile(file)
        setFilePreviewError('')

        // Determine file type from extension
        const extension = file.name.split('.').pop()?.toLowerCase() || ''
        const detectedType = FILE_EXTENSIONS[extension] || 'unknown'
        setFileType(detectedType)

        // Read file content based on type
        const reader = new FileReader()

        // For text-based files, read as text
        if (['text', 'csv', 'json'].includes(detectedType)) {
            reader.onload = (event) => {
                try {
                    const content = event.target?.result as string
                    setFileContent(content)
                } catch (error) {
                    setFilePreviewError('Ошибка чтения файла')
                    console.error('File read error:', error)
                }
            }
            reader.onerror = () => {
                setFilePreviewError('Не удалось прочитать файл')
            }
            reader.readAsText(file)
        }
        // For binary files (PDF, DOCX, XLSX), read as ArrayBuffer for future processing
        else if (['pdf', 'docx', 'xlsx'].includes(detectedType)) {
            reader.onload = (event) => {
                try {
                    const arrayBuffer = event.target?.result as ArrayBuffer
                    // Convert to base64 for storage
                    const base64 = btoa(
                        new Uint8Array(arrayBuffer).reduce(
                            (data, byte) => data + String.fromCharCode(byte),
                            ''
                        )
                    )
                    setFileContent(base64)
                } catch (error) {
                    setFilePreviewError('Ошибка чтения файла')
                    console.error('File read error:', error)
                }
            }
            reader.onerror = () => {
                setFilePreviewError('Не удалось прочитать файл')
            }
            reader.readAsArrayBuffer(file)
        }
    }

    // TODO: Multi-Agent обработка промптов
    // При создании текстового DataNode, промпт сохраняется в text_content.
    // В будущем Multi-Agent система (Priority 3) будет обрабатывать промпт:
    // - Анализировать характер запроса (генерация данных, сбор из источников, deep research)
    // - Planner Agent делегирует задачи специализированным агентам
    // - Результат обработки сохраняется в DataNode.data
    // См. docs/MULTI_AGENT_SYSTEM.md

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        if (!contextBoardId) {
            console.error('No board ID available')
            return
        }

        // Build data based on source mode
        let dataNodeType: 'text' | 'file' | 'api'
        let data: Record<string, any> | undefined
        let dataSourceType: DataSourceType

        // Type-specific fields
        let textContent_: string | undefined
        let query_: string | undefined
        let fileName_: string | undefined
        let filePath_: string | undefined
        let fileType_: string | undefined
        let fileSize_: number | undefined
        let apiUrl_: string | undefined
        let apiMethod_: string | undefined
        let apiHeaders_: Record<string, any> | undefined
        let apiParams_: Record<string, any> | undefined
        let apiConfig_: Record<string, any> | undefined

        switch (sourceMode) {
            case 'api':
                dataNodeType = 'api'
                dataSourceType = DataSourceType.API_CALL
                try {
                    apiUrl_ = apiEndpoint
                    apiMethod_ = apiMethod
                    apiHeaders_ = apiHeaders ? JSON.parse(apiHeaders) : {}
                    apiParams_ = apiBody ? JSON.parse(apiBody) : {}
                    apiConfig_ = {
                        endpoint: apiEndpoint,
                        method: apiMethod,
                        headers: apiHeaders_,
                        body: apiBody || undefined,
                    }
                } catch (error) {
                    console.error('Invalid JSON in API configuration:', error)
                    return
                }
                break

            case 'file':
                dataNodeType = 'file'
                dataSourceType = DataSourceType.FILE_SYSTEM
                fileName_ = selectedFile?.name || 'unknown'
                fileType_ = selectedFile?.type || fileType
                fileSize_ = selectedFile?.size || 0
                data = {
                    filename: fileName_,
                    file_type: fileType_,
                    file_size: fileSize_,
                    raw_content: fileContent,
                    needs_ai_processing: true,
                }
                break

            case 'text':
                dataNodeType = 'text'
                // Текстовые ноды (промпты) будут обработаны Multi-Agent системой
                // См. docs/MULTI_AGENT_SYSTEM.md
                dataSourceType = DataSourceType.AI_GENERATED
                textContent_ = textContent
                data = {
                    prompt: textContent,
                    needs_multi_agent_processing: true,
                }
                break
        }

        // Calculate position (use canvas center if available, otherwise default)
        const preferredX = canvasCenter?.x ?? 100
        const preferredY = canvasCenter?.y ?? 100

        // Find a free position on the canvas
        const { x, y } = findFreePosition(
            dataNodes,
            preferredX,
            preferredY,
            'contentNode'
        )

        // Remove undefined fields to avoid sending them to backend
        const payload: any = {
            name,
            data_source_type: dataSourceType,
            data_node_type: dataNodeType,
            x,
            y,
        }

        // Add optional fields only if they have values
        if (description) payload.description = description
        if (data) payload.data = data
        if (textContent_) payload.text_content = textContent_
        if (query_) payload.query = query_
        if (fileName_) payload.file_name = fileName_
        if (filePath_) payload.file_path = filePath_
        if (fileType_) payload.file_type = fileType_
        if (fileSize_ !== undefined) payload.file_size = fileSize_
        if (apiUrl_) payload.api_url = apiUrl_
        if (apiMethod_) payload.api_method = apiMethod_
        if (apiHeaders_) payload.api_headers = apiHeaders_
        if (apiParams_) payload.api_params = apiParams_
        if (apiConfig_) payload.api_config = apiConfig_

        const dataNode = await createDataNode(contextBoardId, payload)

        if (dataNode) {
            handleClose()
        }
    }

    const handleClose = () => {
        setName('')
        setDescription('')
        setSourceMode('text')
        setApiEndpoint('')
        setApiMethod('GET')
        setApiHeaders('{}')
        setApiBody('')
        setSelectedFile(null)
        setFileContent('')
        setFileType('unknown')
        setFilePreviewError('')
        setTextContent('')
        closeCreateDataNodeDialog()
    }

    const renderFilePreview = () => {
        if (!selectedFile || !fileContent) return null

        switch (fileType) {
            case 'text':
            case 'csv':
                return (
                    <div className="space-y-1.5">
                        <Label className="text-sm">Предпросмотр</Label>
                        <Textarea
                            value={fileContent.slice(0, 800) + (fileContent.length > 800 ? '\n...' : '')}
                            readOnly
                            onKeyDown={(e) => e.stopPropagation()}
                            rows={5}
                            className="font-mono text-xs bg-muted"
                        />
                    </div>
                )

            case 'json':
                try {
                    const parsed = JSON.parse(fileContent)
                    const formatted = JSON.stringify(parsed, null, 2)
                    return (
                        <div className="space-y-1.5">
                            <Label className="text-sm flex items-center gap-1.5">
                                Предпросмотр JSON
                                <span className="text-xs text-green-600">✓ Валидный</span>
                            </Label>
                            <Textarea
                                value={formatted.slice(0, 800) + (formatted.length > 800 ? '\n...' : '')}
                                readOnly
                                onKeyDown={(e) => e.stopPropagation()}
                                rows={5}
                                className="font-mono text-xs bg-muted"
                            />
                        </div>
                    )
                } catch (error) {
                    return (
                        <div className="space-y-1.5">
                            <Label className="text-sm flex items-center gap-1.5">
                                Предпросмотр JSON
                                <span className="text-xs text-destructive">⚠ Невалидный</span>
                            </Label>
                            <Textarea
                                value={fileContent.slice(0, 800)}
                                readOnly
                                onKeyDown={(e) => e.stopPropagation()}
                                rows={5}
                                className="font-mono text-xs bg-muted"
                            />
                        </div>
                    )
                }

            case 'pdf':
                return (
                    <div className="p-3 border rounded-md bg-muted/50 flex items-center gap-2.5">
                        <FileText className="h-6 w-6 text-red-500 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium">PDF Document</div>
                            <div className="text-xs text-muted-foreground">
                                {(selectedFile.size / 1024).toFixed(2)} KB • AI извлечет текст и структуру
                            </div>
                        </div>
                    </div>
                )

            case 'docx':
                return (
                    <div className="p-3 border rounded-md bg-muted/50 flex items-center gap-2.5">
                        <FileText className="h-6 w-6 text-blue-500 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium">Word Document</div>
                            <div className="text-xs text-muted-foreground">
                                {(selectedFile.size / 1024).toFixed(2)} KB • AI извлечет текст и таблицы
                            </div>
                        </div>
                    </div>
                )

            case 'xlsx':
                return (
                    <div className="p-3 border rounded-md bg-muted/50 flex items-center gap-2.5">
                        <FileSpreadsheet className="h-6 w-6 text-green-500 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium">Excel Spreadsheet</div>
                            <div className="text-xs text-muted-foreground">
                                {(selectedFile.size / 1024).toFixed(2)} KB • AI извлечет данные из всех листов
                            </div>
                        </div>
                    </div>
                )

            default:
                return (
                    <div className="space-y-2">
                        <div className="p-4 border rounded-md bg-muted/50">
                            <div className="text-sm text-muted-foreground">
                                Файл загружен. AI обработает содержимое после создания узла.
                            </div>
                        </div>
                    </div>
                )
        }
    }

    const renderSourceSpecificFields = () => {
        switch (sourceMode) {
            case 'api':
                return (
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="api-endpoint">API Endpoint *</Label>
                            <Input
                                id="api-endpoint"
                                placeholder="https://api.example.com/data"
                                value={apiEndpoint}
                                onChange={(e) => setApiEndpoint(e.target.value)}
                                onKeyDown={(e) => e.stopPropagation()}
                                required
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="api-method">HTTP Method</Label>
                            <select
                                id="api-method"
                                value={apiMethod}
                                onChange={(e) => setApiMethod(e.target.value)}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            >
                                <option value="GET">GET</option>
                                <option value="POST">POST</option>
                                <option value="PUT">PUT</option>
                                <option value="DELETE">DELETE</option>
                            </select>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="api-headers">Headers (JSON)</Label>
                            <Textarea
                                id="api-headers"
                                placeholder='{"Authorization": "Bearer token"}'
                                value={apiHeaders}
                                onChange={(e) => setApiHeaders(e.target.value)}
                                onKeyDown={(e) => e.stopPropagation()}
                                rows={2}
                                className="font-mono text-sm"
                            />
                        </div>

                        {apiMethod !== 'GET' && (
                            <div className="space-y-2">
                                <Label htmlFor="api-body">Request Body (JSON)</Label>
                                <Textarea
                                    id="api-body"
                                    placeholder='{"key": "value"}'
                                    value={apiBody}
                                    onChange={(e) => setApiBody(e.target.value)}
                                    onKeyDown={(e) => e.stopPropagation()}
                                    rows={3}
                                    className="font-mono text-sm"
                                />
                            </div>
                        )}
                    </div>
                )

            case 'file':
                return (
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="file-upload">Выберите файл *</Label>
                            <Input
                                id="file-upload"
                                type="file"
                                accept=".txt,.csv,.json,.pdf,.doc,.docx,.xls,.xlsx"
                                onChange={handleFileSelect}
                                className="cursor-pointer"
                            />
                            <p className="text-xs text-muted-foreground">
                                Поддерживаются: TXT, CSV, JSON, PDF, DOCX, XLSX
                            </p>
                            {selectedFile && (
                                <div className="flex items-center gap-2 p-3 border rounded-md bg-muted/50">
                                    {(() => {
                                        const Icon = FILE_ICONS[fileType]
                                        return <Icon className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                                    })()}
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm font-medium truncate">{selectedFile.name}</div>
                                        <div className="text-xs text-muted-foreground">
                                            {fileType.toUpperCase()} • {(selectedFile.size / 1024).toFixed(2)} KB
                                        </div>
                                    </div>
                                </div>
                            )}
                            {filePreviewError && (
                                <div className="text-sm text-destructive">
                                    ⚠️ {filePreviewError}
                                </div>
                            )}
                        </div>

                        {renderFilePreview()}
                    </div>
                )

            case 'text':
                return (
                    <div className="space-y-3">
                        <div className="space-y-1.5">
                            <Label htmlFor="text-content">Содержимое *</Label>
                            <Textarea
                                id="text-content"
                                placeholder="Например: 'Сгенерируй данные о продажах за последние 30 дней' или вставьте любой текстовый контент"
                                value={textContent}
                                onChange={(e) => setTextContent(e.target.value)}
                                onKeyDown={(e) => e.stopPropagation()}
                                rows={6}
                                className="font-mono text-sm"
                                required
                            />
                        </div>

                        <p className="text-xs text-muted-foreground">
                            💡 Промпт будет обработан Multi-Agent системой после создания узла
                        </p>
                    </div>
                )
        }
    }

    return (
        <Dialog open={isCreateDataNodeDialogOpen} onOpenChange={handleClose}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Создать источник данных</DialogTitle>
                    <DialogDescription>
                        Выберите тип источника или перетащите файл на канвас
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit}>
                    <div className="space-y-4 py-3">
                        {/* Basic fields */}
                        <div className="space-y-2">
                            <Label htmlFor="node-name">Название *</Label>
                            <Input
                                id="node-name"
                                placeholder="Например: Пользователи из БД"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                onKeyDown={(e) => e.stopPropagation()}
                                required
                                autoFocus
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="node-description" className="flex items-center gap-1.5 text-sm">
                                Описание
                                <span className="text-xs font-normal text-muted-foreground">
                                    (AI сгенерирует)
                                </span>
                            </Label>
                            <Textarea
                                id="node-description"
                                placeholder="Оставьте пустым - AI создаст описание автоматически"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                onKeyDown={(e) => e.stopPropagation()}
                                rows={1}
                            />
                        </div>

                        {/* Source mode selector */}
                        <div className="space-y-2">
                            <Label>Тип источника *</Label>
                            <div className="grid grid-cols-3 gap-2">
                                {(Object.keys(sourceModes) as SimpleSourceMode[]).map((mode) => {
                                    const config = sourceModes[mode]
                                    const Icon = config.icon
                                    const isSelected = sourceMode === mode

                                    return (
                                        <button
                                            key={mode}
                                            type="button"
                                            onClick={() => {
                                                setSourceMode(mode)
                                                setSelectedFile(null)
                                                setFileContent('')
                                                setTextContent('')
                                            }}
                                            className={`
                                                flex flex-col items-center gap-2 p-4 rounded-md border text-center
                                                transition-colors
                                                ${isSelected
                                                    ? 'border-primary bg-primary/10 text-primary'
                                                    : 'border-input hover:border-primary/50 hover:bg-accent'
                                                }
                                            `}
                                        >
                                            <Icon className="h-6 w-6" />
                                            <span className="text-sm font-medium">{config.label}</span>
                                        </button>
                                    )
                                })}
                            </div>

                        </div>

                        {/* Source-specific fields */}
                        {renderSourceSpecificFields()}
                    </div>

                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={handleClose}
                            disabled={isLoading}
                        >
                            Отмена
                        </Button>
                        <Button
                            type="submit"
                            disabled={isLoading || !name.trim()}
                        >
                            {isLoading ? 'Создание...' : 'Создать источник'}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
