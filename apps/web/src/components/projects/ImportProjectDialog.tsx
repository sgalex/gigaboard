import { useRef, useState } from 'react'
import { Loader2, Upload } from 'lucide-react'
import { Button, buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useProjectStore } from '@/store/projectStore'
import { notify } from '@/store/notificationStore'
import type { Project } from '@/types'

type ImportProjectDialogProps = {
    open: boolean
    onOpenChange: (open: boolean) => void
    /** После успешного импорта (например, перейти в проект). */
    onImported?: (project: Project) => void
}

export function ImportProjectDialog({ open, onOpenChange, onImported }: ImportProjectDialogProps) {
    const importProjectFromZip = useProjectStore((s) => s.importProjectFromZip)
    const [name, setName] = useState('')
    const [busy, setBusy] = useState(false)
    const inputRef = useRef<HTMLInputElement>(null)
    const [pickedLabel, setPickedLabel] = useState<string | null>(null)

    const reset = () => {
        setName('')
        setPickedLabel(null)
        setBusy(false)
        if (inputRef.current) inputRef.current.value = ''
    }

    const handleOpenChange = (next: boolean) => {
        if (!next && busy) return
        if (!next) reset()
        onOpenChange(next)
    }

    const onPickFile = () => inputRef.current?.click()

    const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const f = e.target.files?.[0]
        setPickedLabel(f ? f.name : null)
    }

    const submit = async () => {
        const file = inputRef.current?.files?.[0]
        if (!file) return
        if (!file.name.toLowerCase().endsWith('.zip')) {
            notify.error('Нужен файл с расширением .zip', { title: 'Импорт' })
            return
        }
        setBusy(true)
        try {
            const project = await importProjectFromZip(file, name.trim() || undefined)
            if (project) {
                reset()
                onOpenChange(false)
                onImported?.(project)
            }
        } finally {
            setBusy(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent
                className="w-[calc(100vw-2rem)] max-w-md overflow-hidden sm:w-full"
                onClick={(e) => e.stopPropagation()}
                onPointerDownOutside={(e) => busy && e.preventDefault()}
                onEscapeKeyDown={(e) => busy && e.preventDefault()}
            >
                <DialogHeader>
                    <DialogTitle>Импорт проекта из ZIP</DialogTitle>
                </DialogHeader>
                <div className="grid min-w-0 max-w-full gap-4 py-2">
                    <p className="min-w-0 break-words text-sm text-muted-foreground">
                        Выберите архив, сохранённый через «Экспорт» на этом сервере. Будет создан{' '}
                        <strong>новый</strong> проект у вашей учётной записи.
                    </p>
                    <input
                        ref={inputRef}
                        type="file"
                        accept=".zip,application/zip"
                        className="sr-only"
                        onChange={onFileChange}
                    />
                    <div className="grid min-w-0 gap-2">
                        <Label>Файл архива</Label>
                        <button
                            type="button"
                            onClick={onPickFile}
                            className={cn(
                                buttonVariants({ variant: 'outline', size: 'default' }),
                                'flex h-auto min-h-10 w-full min-w-0 max-w-full items-center justify-start gap-2 overflow-hidden py-2 text-left whitespace-normal'
                            )}
                        >
                            <Upload className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                            <span className="min-w-0 flex-1 truncate">
                                {pickedLabel || 'Выбрать .zip…'}
                            </span>
                        </button>
                    </div>
                    <div className="grid min-w-0 gap-2">
                        <Label htmlFor="import-project-name">Название проекта (необязательно)</Label>
                        <Input
                            id="import-project-name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Если пусто — из архива с суффиксом «(import)»"
                            disabled={busy}
                            className="min-w-0 max-w-full"
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={busy}>
                        Отмена
                    </Button>
                    <Button type="button" onClick={submit} disabled={busy || !pickedLabel}>
                        {busy ? 'Импорт…' : 'Импортировать'}
                    </Button>
                </DialogFooter>

                {busy ? (
                    <div
                        className="absolute inset-0 z-20 flex flex-col items-center justify-center rounded-lg bg-background/85 backdrop-blur-sm"
                        role="status"
                        aria-live="polite"
                        aria-busy="true"
                    >
                        <Loader2 className="h-10 w-10 animate-spin text-primary" aria-hidden />
                        <p className="mt-4 text-sm font-medium text-foreground">Импорт проекта…</p>
                        <p className="mt-1 max-w-[240px] text-center text-xs text-muted-foreground">
                            Загрузка и восстановление данных, подождите.
                        </p>
                    </div>
                ) : null}
            </DialogContent>
        </Dialog>
    )
}
