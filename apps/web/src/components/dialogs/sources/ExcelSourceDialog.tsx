/**
 * Excel Source Dialog - диалог для загрузки Excel файлов.
 */
import { useState, useEffect } from 'react'
import { FileSpreadsheet } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { filesAPI } from '@/services/api'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'

export function ExcelSourceDialog({
    open,
    onOpenChange,
    initialPosition,
    existingSource,
    mode = 'create'
}: SourceDialogProps) {
    const [file, setFile] = useState<File | null>(null)
    const [isUploading, setIsUploading] = useState(false)
    const [hasHeader, setHasHeader] = useState<boolean>(true)
    const [maxRows, setMaxRows] = useState<string>('')
    const [filename, setFilename] = useState<string>('')

    const { isLoading, create, update } = useSourceDialog({
        sourceType: SourceType.EXCEL,
        onClose: () => {
            setFile(null)
            onOpenChange(false)
        },
        position: initialPosition,
    })

    // Load existing data in edit mode
    useEffect(() => {
        if (mode === 'edit' && existingSource && open) {
            const config = existingSource.config
            setHasHeader(config.has_header !== undefined ? config.has_header : true)
            setMaxRows(config.max_rows ? String(config.max_rows) : '')
            setFilename(config.filename || existingSource.metadata?.name || '')
        }
    }, [mode, existingSource, open])

    const handleSubmit = async () => {
        if (mode === 'edit' && existingSource) {
            // Edit mode: update existing source
            const config: any = {
                file_id: existingSource.config.file_id,
                filename: existingSource.config.filename,
                mime_type: existingSource.config.mime_type,
                size_bytes: existingSource.config.size_bytes,
                sheets: existingSource.config.sheets || [],
                has_header: hasHeader,
            }
            if (maxRows && maxRows.trim() !== '') {
                config.max_rows = parseInt(maxRows, 10)
            }

            const metadata: any = {
                name: filename || existingSource.metadata?.name || '',
            }

            await update(existingSource.id, config, metadata)
            return
        }

        // Create mode: upload file
        if (!file) {
            notify.error('Выберите Excel файл')
            return
        }

        setIsUploading(true)
        try {
            notify.info('Загрузка файла...')
            const uploadResponse = await filesAPI.upload(file)
            const uploadedFile = uploadResponse.data

            notify.success(`Файл "${file.name}" загружен`)

            const config: any = {
                file_id: uploadedFile.file_id,
                filename: uploadedFile.filename,
                mime_type: uploadedFile.mime_type,
                size_bytes: uploadedFile.size_bytes,
                sheets: [], // All sheets by default
                has_header: hasHeader,
            }
            if (maxRows && maxRows.trim() !== '') {
                config.max_rows = parseInt(maxRows, 10)
            }

            await create(config, {
                name: filename || file.name,
            })
        } catch (error) {
            notify.error('Не удалось загрузить файл')
            console.error('File upload error:', error)
        } finally {
            setIsUploading(false)
        }
    }

    const dialogTitle = mode === 'edit' ? 'Редактирование Excel источника' : 'Excel файл'
    const dialogDescription = mode === 'edit'
        ? 'Изменение параметров извлечения данных из Excel файла'
        : 'Загрузите Excel файл — поддержка нескольких листов'
    const isValid = mode === 'edit' ? !!filename : !!file

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title={dialogTitle}
            description={dialogDescription}
            icon={<FileSpreadsheet className="h-5 w-5 text-emerald-600" />}
            isLoading={isLoading || isUploading}
            isValid={isValid}
            onSubmit={handleSubmit}
            submitLabel={mode === 'edit' ? 'Сохранить' : 'Создать'}
        >
            <div className="space-y-4">
                {mode === 'create' && (
                    <div className="space-y-2">
                        <Label htmlFor="excel-file">Выберите Excel файл *</Label>
                        <Input
                            id="excel-file"
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={(e) => setFile(e.target.files?.[0] || null)}
                            className="cursor-pointer"
                        />
                        {file && (
                            <p className="text-xs text-muted-foreground">
                                Выбран: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                            </p>
                        )}
                    </div>
                )}

                {mode === 'edit' && (
                    <div className="space-y-2">
                        <Label htmlFor="excel-filename">Имя источника *</Label>
                        <Input
                            id="excel-filename"
                            value={filename}
                            onChange={(e) => setFilename(e.target.value)}
                            placeholder="Название источника данных"
                        />
                    </div>
                )}

                <div className="flex items-center space-x-2">
                    <Checkbox
                        id="excel-has-header"
                        checked={hasHeader}
                        onCheckedChange={(checked) => setHasHeader(checked === true)}
                    />
                    <Label htmlFor="excel-has-header" className="cursor-pointer">
                        Первая строка - заголовки
                    </Label>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="excel-max-rows">Ограничение строк (опционально)</Label>
                    <Input
                        id="excel-max-rows"
                        type="number"
                        value={maxRows}
                        onChange={(e) => setMaxRows(e.target.value)}
                        placeholder="Без ограничений"
                        min="1"
                    />
                    <p className="text-xs text-muted-foreground">
                        Оставьте пустым для загрузки всех данных
                    </p>
                </div>

                <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
                    <p className="font-medium mb-2">Возможности:</p>
                    <ul className="list-disc list-inside space-y-1">
                        <li>Извлечение всех листов</li>
                        <li>Выбор конкретных листов</li>
                        <li>AI-помощник для сложных структур</li>
                    </ul>
                </div>
            </div>
        </BaseSourceDialog>
    )
}
