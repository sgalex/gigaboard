/**
 * CSV Source Dialog - полноценный диалог для загрузки CSV файлов с AI-анализом.
 * См. docs/SOURCE_NODE_CONCEPT.md - раздел "📊 1. CSV Dialog"
 */
import { useState, useCallback, useEffect } from 'react'
import { FileSpreadsheet, Upload, Check, X, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { filesAPI } from '@/services/api'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'

interface CSVAnalysisResult {
    delimiter: string
    encoding: string
    has_header: boolean
    rows_count: number
    columns: Array<{
        name: string
        type: string
        sample_values: string[]
    }>
    preview_rows: Array<Record<string, any>>
    file_id?: string  // Added to store uploaded file ID
}

export function CSVSourceDialog({ open, onOpenChange, initialPosition, existingSource, mode = 'create' }: SourceDialogProps) {
    const [file, setFile] = useState<File | null>(null)
    const [isUploading, setIsUploading] = useState(false)
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [analysisResult, setAnalysisResult] = useState<CSVAnalysisResult | null>(null)
    const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set())
    const [columnRenames, setColumnRenames] = useState<Record<string, string>>({})
    const [editingColumn, setEditingColumn] = useState<string | null>(null)
    const [showManualSettings, setShowManualSettings] = useState(false)

    // Manual settings
    const [manualDelimiter, setManualDelimiter] = useState<string>(',')
    const [manualEncoding, setManualEncoding] = useState<string>('utf-8')
    const [manualHasHeader, setManualHasHeader] = useState<boolean>(true)

    const { isLoading, create, update } = useSourceDialog({
        sourceType: SourceType.CSV,
        onClose: () => {
            resetForm()
            onOpenChange(false)
        },
        position: initialPosition,
    })

    // Load existing source data in edit mode
    useEffect(() => {
        if (mode === 'edit' && existingSource && open) {
            const config = existingSource.config

            // Pre-fill analysis result from existing data
            const mockResult: CSVAnalysisResult = {
                delimiter: config.delimiter || ',',
                encoding: config.encoding || 'utf-8',
                has_header: config.has_header !== undefined ? config.has_header : true,
                rows_count: config.rows_count || 0,
                columns: existingSource.content?.tables?.[0]?.columns?.map((col: any) => ({
                    name: col.name,
                    type: 'текст',
                    sample_values: []
                })) || [],
                preview_rows: existingSource.content?.tables?.[0]?.rows?.slice(0, 10) || [],
                file_id: config.file_id
            }

            setAnalysisResult(mockResult)
            setManualDelimiter(config.delimiter || ',')
            setManualEncoding(config.encoding || 'utf-8')
            setManualHasHeader(config.has_header !== undefined ? config.has_header : true)

            // Pre-select columns if specified
            if (config.selected_columns && Array.isArray(config.selected_columns)) {
                setSelectedColumns(new Set(config.selected_columns))
            }
        }
    }, [mode, existingSource, open])

    const resetForm = () => {
        setFile(null)
        setAnalysisResult(null)
        setSelectedColumns(new Set())
        setColumnRenames({})
        setEditingColumn(null)
        setShowManualSettings(false)
    }

    const handleFileDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        const droppedFile = e.dataTransfer.files[0]
        if (droppedFile && droppedFile.name.endsWith('.csv')) {
            setFile(droppedFile)
            analyzeFile(droppedFile)
        } else {
            notify.error('Только CSV файлы')
        }
    }, [])

    const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0]
        if (selectedFile) {
            setFile(selectedFile)
            analyzeFile(selectedFile)
        }
    }, [])

    const analyzeFile = async (file: File, customDelimiter?: string, customEncoding?: string, customHasHeader?: boolean) => {
        setIsAnalyzing(true)
        try {
            // First, upload the file to get file_id
            notify.info('Загрузка файла...')
            const uploadResponse = await filesAPI.upload(file)
            const uploadedFile = uploadResponse.data

            // If manual settings provided, use client-side analysis
            if (customDelimiter || customEncoding || customHasHeader !== undefined) {
                // Client-side re-analysis with custom settings
                const chunk = file.slice(0, 100 * 1024)
                const arrayBuffer = await chunk.arrayBuffer()

                const encoding = customEncoding || 'utf-8'
                const decoder = new TextDecoder(encoding)
                const text = decoder.decode(arrayBuffer)

                const lines = text.split('\n').filter(l => l.trim())
                if (lines.length === 0) {
                    throw new Error('Пустой файл')
                }

                const firstLine = lines[0]
                const delimiter = customDelimiter || ','
                const actualDelimiter = delimiter === 'tab' ? '\t' : delimiter
                const hasHeader = customHasHeader !== undefined ? customHasHeader : true

                const headerLine = hasHeader ? firstLine : ''
                const headers = hasHeader
                    ? headerLine.split(actualDelimiter).map(h => h.trim().replace(/^["']|["']$/g, ''))
                    : Array.from({ length: firstLine.split(actualDelimiter).length }, (_, i) => `Column ${i + 1}`)

                const dataStartIdx = hasHeader ? 1 : 0
                const dataLines = lines.slice(dataStartIdx, Math.min(dataStartIdx + 10, lines.length))
                const previewRows = dataLines.map(line => {
                    const values = line.split(actualDelimiter).map(v => v.trim().replace(/^["']|["']$/g, ''))
                    const row: Record<string, any> = {}
                    headers.forEach((h, i) => {
                        row[h] = values[i] || ''
                    })
                    return row
                })

                const columns = headers.map((name) => {
                    const samples = previewRows.map(row => row[name]).filter(Boolean)
                    const isNumeric = samples.every(v => !isNaN(Number(v)))
                    const isDate = samples.some(v => /^\d{4}-\d{2}-\d{2}/.test(v))

                    return {
                        name,
                        type: isDate ? 'дата' : isNumeric ? 'число' : 'текст',
                        sample_values: samples.slice(0, 3)
                    }
                })

                const result: CSVAnalysisResult = {
                    delimiter: delimiter === '\t' ? 'tab' : delimiter,
                    encoding,
                    has_header: hasHeader,
                    rows_count: lines.length - (hasHeader ? 1 : 0),
                    columns,
                    preview_rows: previewRows,
                    file_id: uploadedFile.file_id
                }

                setAnalysisResult(result)
                setSelectedColumns(new Set(headers))
                notify.success('Настройки применены')
            } else {
                // Use backend AI analysis
                notify.info('AI анализирует CSV...')
                const analysisResponse = await filesAPI.analyzeCSV(uploadedFile.file_id)
                const backendResult = analysisResponse.data

                const result: CSVAnalysisResult = {
                    ...backendResult,
                    file_id: uploadedFile.file_id
                }

                setAnalysisResult(result)
                setSelectedColumns(new Set(backendResult.columns.map(c => c.name)))

                // Update manual settings with detected values
                setManualDelimiter(backendResult.delimiter)
                setManualEncoding(backendResult.encoding)
                setManualHasHeader(backendResult.has_header)

                notify.success(`AI определил: ${backendResult.delimiter === 'tab' ? 'табуляция' : backendResult.delimiter}, ${backendResult.encoding.toUpperCase()}`)
            }
        } catch (error) {
            notify.error('Ошибка анализа файла')
            console.error('CSV analysis error:', error)
        } finally {
            setIsAnalyzing(false)
        }
    }

    const reanalyzeWithManualSettings = () => {
        if (!file) return
        analyzeFile(file, manualDelimiter, manualEncoding, manualHasHeader)
    }

    const toggleColumn = (columnName: string) => {
        setSelectedColumns(prev => {
            const newSet = new Set(prev)
            if (newSet.has(columnName)) {
                newSet.delete(columnName)
            } else {
                newSet.add(columnName)
            }
            return newSet
        })
    }

    const getDisplayName = (originalName: string) => columnRenames[originalName] || originalName

    const commitRename = (originalName: string, newName: string) => {
        const trimmed = newName.trim()
        setColumnRenames(prev => {
            const next = { ...prev }
            if (!trimmed || trimmed === originalName) {
                delete next[originalName]
            } else {
                next[originalName] = trimmed
            }
            return next
        })
        setEditingColumn(null)
    }

    const handleSubmit = async () => {
        if (!analysisResult) {
            notify.error(mode === 'edit' ? 'Данные не загружены' : 'Загрузите и проанализируйте CSV файл')
            return
        }

        if (selectedColumns.size === 0) {
            notify.error('Выберите хотя бы один столбец')
            return
        }

        setIsUploading(true)
        try {
            const config = {
                file_id: analysisResult.file_id,
                filename: file?.name || existingSource?.config?.filename || 'file.csv',
                delimiter: showManualSettings ? manualDelimiter : analysisResult.delimiter,
                encoding: showManualSettings ? manualEncoding : analysisResult.encoding,
                has_header: showManualSettings ? manualHasHeader : analysisResult.has_header,
                selected_columns: Array.from(selectedColumns),
                column_renames: Object.keys(columnRenames).length > 0 ? columnRenames : undefined,
                rows_count: analysisResult.rows_count,
            }

            const metadata = {
                name: file?.name.replace('.csv', '') || existingSource?.metadata?.name || 'CSV Source',
            }

            if (mode === 'edit' && existingSource) {
                // Update existing source
                await update(existingSource.id, config, metadata)
            } else {
                // Create new source
                if (!file) {
                    notify.error('Загрузите CSV файл')
                    return
                }

                // File already uploaded during analysis, reuse file_id
                let fileId = analysisResult.file_id

                // If file_id not available, upload now
                if (!fileId) {
                    notify.info('Загрузка файла...')
                    const uploadResponse = await filesAPI.upload(file)
                    fileId = uploadResponse.data.file_id
                    config.file_id = fileId
                }

                await create(config, metadata)
                notify.success(`Источник "${file.name}" создан`)
            }
        } catch (error) {
            notify.error(mode === 'edit' ? 'Не удалось обновить источник' : 'Не удалось создать источник')
            console.error('CSV source error:', error)
        } finally {
            setIsUploading(false)
        }
    }

    const isValid = mode === 'edit' ? (!!analysisResult && selectedColumns.size > 0) : (!!file && !!analysisResult && selectedColumns.size > 0)

    const dialogTitle = mode === 'edit'
        ? `Настройки CSV — ${existingSource?.metadata?.name || 'источник'}`
        : `CSV — ${file?.name || 'загрузите файл'}`

    const dialogDescription = mode === 'edit'
        ? 'Редактирование настроек источника данных'
        : 'Автоматический анализ и извлечение данных'

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title={dialogTitle}
            description={dialogDescription}
            icon={<FileSpreadsheet className="h-5 w-5 text-green-500" />}
            isLoading={isLoading || isUploading}
            isValid={isValid}
            onSubmit={handleSubmit}
            submitLabel={mode === 'edit' ? 'Сохранить' : 'Создать'}
            className="max-w-6xl"
            contentClassName="overflow-hidden"
        >
            <div className="grid grid-cols-2 gap-6 flex-1 min-h-0">
                {/* Left Panel - Upload & Analysis */}
                <div className="flex flex-col gap-4 min-h-0 overflow-y-auto">
                    {/* Drag & Drop Zone (only in create mode) */}
                    {!file && mode === 'create' && (
                        <div
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={handleFileDrop}
                            className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer shrink-0"
                            onClick={() => document.getElementById('csv-file-input')?.click()}
                        >
                            <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                            <p className="text-sm font-medium mb-1">Перетащите CSV файл сюда</p>
                            <p className="text-xs text-muted-foreground">или нажмите для выбора</p>
                            <Input
                                id="csv-file-input"
                                type="file"
                                accept=".csv"
                                onChange={handleFileSelect}
                                className="hidden"
                            />
                        </div>
                    )}

                    {/* File Info */}
                    {file && (
                        <div className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg shrink-0">
                            <FileSpreadsheet className="h-4 w-4 text-green-500" />
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{file.name}</p>
                                <p className="text-xs text-muted-foreground">
                                    {(file.size / 1024).toFixed(2)} KB
                                </p>
                            </div>
                            {!isAnalyzing && (
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => {
                                        setFile(null)
                                        setAnalysisResult(null)
                                    }}
                                >
                                    <X className="h-4 w-4" />
                                </Button>
                            )}
                        </div>
                    )}

                    {/* AI Analysis Results */}
                    {isAnalyzing && (
                        <div className="flex items-center gap-3 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg shrink-0">
                            <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                            <span className="text-sm">Анализ файла...</span>
                        </div>
                    )}

                    {analysisResult && !isAnalyzing && (
                        <div className="space-y-2 p-4 bg-green-500/10 border border-green-500/20 rounded-lg shrink-0">
                            <div className="flex items-center gap-2 mb-3">
                                <Check className="h-5 w-5 text-green-500" />
                                <span className="font-medium text-sm">AI-анализ завершён</span>
                            </div>
                            <div className="space-y-1 text-sm">
                                <div className="flex items-center gap-2">
                                    <Check className="h-3 w-3 text-green-500" />
                                    <span>Разделитель: {analysisResult.delimiter === 'tab' ? 'табуляция' : analysisResult.delimiter}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Check className="h-3 w-3 text-green-500" />
                                    <span>Кодировка: {analysisResult.encoding.toUpperCase()}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Check className="h-3 w-3 text-green-500" />
                                    <span>Заголовки: {analysisResult.has_header ? 'первая строка' : 'нет'}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Check className="h-3 w-3 text-green-500" />
                                    <span>Строк: {analysisResult.rows_count.toLocaleString()}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Check className="h-3 w-3 text-green-500" />
                                    <span>Столбцов: {analysisResult.columns.length}</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Manual Settings (Collapsible) */}
                    {analysisResult && (
                        <div className="border border-border rounded-lg shrink-0">
                            <button
                                className="w-full flex items-center gap-2 p-3 hover:bg-muted/50 transition-colors"
                                onClick={() => setShowManualSettings(!showManualSettings)}
                            >
                                {showManualSettings ? (
                                    <ChevronDown className="h-4 w-4" />
                                ) : (
                                    <ChevronRight className="h-4 w-4" />
                                )}
                                <span className="text-sm font-medium">Ручные настройки</span>
                                <span className="text-xs text-muted-foreground">(если AI ошибся)</span>
                            </button>

                            {showManualSettings && (
                                <div className="p-4 space-y-3 border-t">
                                    <div className="space-y-2">
                                        <Label>Разделитель</Label>
                                        <Select value={manualDelimiter} onValueChange={setManualDelimiter}>
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value=",">,  (запятая)</SelectItem>
                                                <SelectItem value=";">; (точка с запятой)</SelectItem>
                                                <SelectItem value="tab">Tab (табуляция)</SelectItem>
                                                <SelectItem value="|">| (вертикальная черта)</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Кодировка</Label>
                                        <Select value={manualEncoding} onValueChange={setManualEncoding}>
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="utf-8">UTF-8</SelectItem>
                                                <SelectItem value="windows-1251">Windows-1251</SelectItem>
                                                <SelectItem value="latin1">Latin-1</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Checkbox
                                            id="has-header"
                                            checked={manualHasHeader}
                                            onCheckedChange={(checked: boolean) => setManualHasHeader(checked)}
                                        />
                                        <Label htmlFor="has-header" className="cursor-pointer">
                                            Первая строка — заголовки
                                        </Label>
                                    </div>
                                    <Button
                                        onClick={reanalyzeWithManualSettings}
                                        disabled={isAnalyzing || !file}
                                        className="w-full"
                                        variant="secondary"
                                    >
                                        {isAnalyzing ? (
                                            <>
                                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                Применяю...
                                            </>
                                        ) : (
                                            <>
                                                <Check className="h-4 w-4 mr-2" />
                                                Применить настройки
                                            </>
                                        )}
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Right Panel - Column Selection & Preview */}
                <div className="flex flex-col gap-3 min-h-0 overflow-hidden">
                    {analysisResult && (
                        <>
                            {/* Column Selection - compact chips */}
                            <div className="shrink-0">
                                <div className="flex items-baseline justify-between mb-1.5">
                                    <h4 className="text-sm font-medium">Выбор столбцов</h4>
                                    <p className="text-xs text-muted-foreground">
                                        Выбрано: {selectedColumns.size} из {analysisResult.columns.length}
                                    </p>
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                    {analysisResult.columns.map((col) => {
                                        const isSelected = selectedColumns.has(col.name)
                                        return (
                                            <button
                                                key={col.name}
                                                type="button"
                                                onClick={() => toggleColumn(col.name)}
                                                className={`
                                                    inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium
                                                    border transition-colors cursor-pointer select-none
                                                    ${isSelected
                                                        ? 'bg-primary/10 border-primary/40 text-primary hover:bg-primary/20'
                                                        : 'bg-muted/40 border-border text-muted-foreground hover:bg-muted/80 line-through opacity-60'
                                                    }
                                                `}
                                                title={`${col.name} — ${col.type}`}
                                            >
                                                {isSelected && <Check className="h-3 w-3 shrink-0" />}
                                                <span className="truncate max-w-[140px]">{getDisplayName(col.name)}</span>
                                                <span className="text-[10px] opacity-60">{col.type}</span>
                                            </button>
                                        )
                                    })}
                                </div>
                            </div>

                            {/* Preview Table */}
                            <div className="border border-border rounded-lg flex flex-col min-h-0 flex-1">
                                <div className="p-3 border-b bg-muted/50 shrink-0">
                                    <h4 className="text-sm font-medium">Предпросмотр данных</h4>
                                    <p className="text-xs text-muted-foreground">
                                        Показано {analysisResult.preview_rows.length} из {analysisResult.rows_count}
                                    </p>
                                </div>
                                <div className="overflow-auto flex-1">
                                    <table className="w-full text-xs">
                                        <thead className="bg-muted/50 sticky top-0">
                                            <tr>
                                                {Array.from(selectedColumns).map((col) => (
                                                    <th key={col} className="p-2 text-left font-medium border-b">
                                                        {editingColumn === col ? (
                                                            <input
                                                                type="text"
                                                                autoFocus
                                                                defaultValue={getDisplayName(col)}
                                                                className="bg-transparent border-b-2 border-primary outline-none text-xs font-medium w-full min-w-[60px]"
                                                                onBlur={(e) => commitRename(col, e.target.value)}
                                                                onKeyDown={(e) => {
                                                                    if (e.key === 'Enter') commitRename(col, e.currentTarget.value)
                                                                    if (e.key === 'Escape') setEditingColumn(null)
                                                                }}
                                                                onClick={(e) => e.stopPropagation()}
                                                            />
                                                        ) : (
                                                            <span
                                                                className="cursor-pointer hover:text-primary transition-colors"
                                                                onClick={() => setEditingColumn(col)}
                                                                title="Нажмите для переименования"
                                                            >
                                                                {getDisplayName(col)}
                                                            </span>
                                                        )}
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {analysisResult.preview_rows.map((row, idx) => (
                                                <tr key={idx} className="border-b hover:bg-muted/30">
                                                    {Array.from(selectedColumns).map((col) => (
                                                        <td key={col} className="p-2 truncate max-w-[150px]">
                                                            {row[col]}
                                                        </td>
                                                    ))}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </>
                    )}

                    {!analysisResult && !isAnalyzing && (
                        <div className="flex items-center justify-center h-full text-muted-foreground">
                            <p className="text-sm">Загрузите файл для начала анализа</p>
                        </div>
                    )}
                </div>
            </div>
        </BaseSourceDialog>
    )
}
