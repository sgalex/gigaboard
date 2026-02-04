/**
 * API Source Dialog - диалог для REST API источника.
 */
import { useState } from 'react'
import { Globe } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'

export function APISourceDialog({ open, onOpenChange, initialPosition }: SourceDialogProps) {
    const [url, setUrl] = useState('')
    const [method, setMethod] = useState('GET')
    const [headers, setHeaders] = useState('')
    const [body, setBody] = useState('')

    // Pagination
    const [paginationEnabled, setPaginationEnabled] = useState(false)
    const [paginationType, setPaginationType] = useState('page')
    const [pageParam, setPageParam] = useState('page')
    const [sizeParam, setSizeParam] = useState('per_page')
    const [pageSize, setPageSize] = useState('100')
    const [maxPages, setMaxPages] = useState('10')

    const { isLoading, create } = useSourceDialog({
        sourceType: SourceType.API,
        onClose: () => {
            resetForm()
            onOpenChange(false)
        },
        position: initialPosition,
    })

    const resetForm = () => {
        setUrl('')
        setMethod('GET')
        setHeaders('')
        setBody('')
        setPaginationEnabled(false)
    }

    const handleSubmit = async () => {
        if (!url.trim()) {
            notify.error('Укажите URL API')
            return
        }

        let parsedHeaders = {}
        if (headers.trim()) {
            try {
                parsedHeaders = JSON.parse(headers)
            } catch {
                notify.error('Неверный формат Headers (должен быть JSON)')
                return
            }
        }

        const config: Record<string, any> = {
            url: url.trim(),
            method,
            headers: parsedHeaders,
        }

        if (body.trim() && ['POST', 'PUT', 'PATCH'].includes(method)) {
            try {
                config.body = JSON.parse(body)
            } catch {
                notify.error('Неверный формат Body (должен быть JSON)')
                return
            }
        }

        if (paginationEnabled) {
            config.pagination = {
                enabled: true,
                type: paginationType,
                page_param: pageParam,
                size_param: sizeParam,
                page_size: parseInt(pageSize),
                max_pages: parseInt(maxPages),
            }
        }

        await create(config, { name: new URL(url).hostname })
    }

    const isValid = url.trim().length > 0

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title="REST API"
            description="Подключитесь к REST API с поддержкой пагинации"
            icon={<Globe className="h-5 w-5 text-purple-500" />}
            isLoading={isLoading}
            isValid={isValid}
            onSubmit={handleSubmit}
        >
            <div className="space-y-4">
                <div className="grid grid-cols-4 gap-4">
                    <div className="col-span-1 space-y-2">
                        <Label>Метод</Label>
                        <Select value={method} onValueChange={setMethod}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="GET">GET</SelectItem>
                                <SelectItem value="POST">POST</SelectItem>
                                <SelectItem value="PUT">PUT</SelectItem>
                                <SelectItem value="PATCH">PATCH</SelectItem>
                                <SelectItem value="DELETE">DELETE</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="col-span-3 space-y-2">
                        <Label htmlFor="api-url">URL *</Label>
                        <Input
                            id="api-url"
                            placeholder="https://api.example.com/data"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                        />
                    </div>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="api-headers">Headers (JSON)</Label>
                    <Textarea
                        id="api-headers"
                        placeholder='{"Authorization": "Bearer token", "Content-Type": "application/json"}'
                        value={headers}
                        onChange={(e) => setHeaders(e.target.value)}
                        rows={2}
                        className="font-mono text-sm"
                    />
                </div>

                {['POST', 'PUT', 'PATCH'].includes(method) && (
                    <div className="space-y-2">
                        <Label htmlFor="api-body">Body (JSON)</Label>
                        <Textarea
                            id="api-body"
                            placeholder='{"query": "value"}'
                            value={body}
                            onChange={(e) => setBody(e.target.value)}
                            rows={3}
                            className="font-mono text-sm"
                        />
                    </div>
                )}

                {/* Pagination */}
                <div className="border rounded-lg p-4 space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <Label className="text-base">Пагинация</Label>
                            <p className="text-xs text-muted-foreground">Автоматическая загрузка всех страниц</p>
                        </div>
                        <Switch
                            checked={paginationEnabled}
                            onCheckedChange={setPaginationEnabled}
                        />
                    </div>

                    {paginationEnabled && (
                        <div className="grid grid-cols-2 gap-4 pt-2">
                            <div className="space-y-2">
                                <Label>Тип пагинации</Label>
                                <Select value={paginationType} onValueChange={setPaginationType}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="page">Page-based</SelectItem>
                                        <SelectItem value="offset">Offset-based</SelectItem>
                                        <SelectItem value="cursor">Cursor-based</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Параметр страницы</Label>
                                <Input
                                    value={pageParam}
                                    onChange={(e) => setPageParam(e.target.value)}
                                    placeholder="page"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Размер страницы</Label>
                                <Input
                                    type="number"
                                    value={pageSize}
                                    onChange={(e) => setPageSize(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Макс. страниц</Label>
                                <Input
                                    type="number"
                                    value={maxPages}
                                    onChange={(e) => setMaxPages(e.target.value)}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </BaseSourceDialog>
    )
}
