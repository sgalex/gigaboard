/**
 * Document Source Dialog - диалог для загрузки документов (PDF, DOCX, TXT).
 */
import { useState } from 'react'
import { FileText } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { filesAPI } from '@/services/api'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'

export function DocumentSourceDialog({ open, onOpenChange, initialPosition }: SourceDialogProps) {
    const [file, setFile] = useState<File | null>(null)
    const [extractionPrompt, setExtractionPrompt] = useState('')
    const [isUploading, setIsUploading] = useState(false)

    const { isLoading, create } = useSourceDialog({
        sourceType: SourceType.DOCUMENT,
        onClose: () => {
            setFile(null)
            setExtractionPrompt('')
            onOpenChange(false)
        },
        position: initialPosition,
    })

    const handleSubmit = async () => {
        if (!file) {
            notify.error('Выберите документ')
            return
        }

        setIsUploading(true)
        try {
            notify.info('Загрузка документа...')
            const uploadResponse = await filesAPI.upload(file)
            const uploadedFile = uploadResponse.data

            notify.success(`Документ "${file.name}" загружен`)

            await create({
                file_id: uploadedFile.file_id,
                filename: uploadedFile.filename,
                mime_type: uploadedFile.mime_type,
                size_bytes: uploadedFile.size_bytes,
                extraction_prompt: extractionPrompt || undefined,
            }, {
                name: file.name,
            })
        } catch (error) {
            notify.error('Не удалось загрузить документ')
            console.error('File upload error:', error)
        } finally {
            setIsUploading(false)
        }
    }

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Документ"
            description="Загрузите PDF, DOCX или TXT — AI извлечёт таблицы и данные"
            icon={<FileText className="h-5 w-5 text-blue-500" />}
            isLoading={isLoading || isUploading}
            isValid={!!file}
            onSubmit={handleSubmit}
        >
            <div className="space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="doc-file">Выберите документ *</Label>
                    <Input
                        id="doc-file"
                        type="file"
                        accept=".pdf,.docx,.txt"
                        onChange={(e) => setFile(e.target.files?.[0] || null)}
                        className="cursor-pointer"
                    />
                    {file && (
                        <p className="text-xs text-muted-foreground">
                            Выбран: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                        </p>
                    )}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="extraction-prompt">Инструкция для извлечения (опционально)</Label>
                    <Textarea
                        id="extraction-prompt"
                        placeholder="Например: Найди все таблицы с финансовыми данными и объедини их..."
                        value={extractionPrompt}
                        onChange={(e) => setExtractionPrompt(e.target.value)}
                        rows={3}
                    />
                </div>

                <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
                    <p className="font-medium mb-2">Multi-Agent извлечение:</p>
                    <ul className="list-disc list-inside space-y-1">
                        <li>Извлечение текста из PDF (включая сканы через OCR)</li>
                        <li>Поиск таблиц в документе</li>
                        <li>Структурирование данных в таблицу</li>
                    </ul>
                </div>
            </div>
        </BaseSourceDialog>
    )
}
