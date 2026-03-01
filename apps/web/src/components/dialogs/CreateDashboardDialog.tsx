/**
 * Create Dashboard Dialog — choose name, canvas preset, etc.
 * See docs/DASHBOARD_SYSTEM.md
 */
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useDashboardStore } from '@/store/dashboardStore'
import { useUIStore } from '@/store/uiStore'
import type { CanvasPreset } from '@/types/dashboard'

const presets: { value: CanvasPreset; label: string; width: number; height: number }[] = [
    { value: 'compact', label: '1200×800', width: 1200, height: 800 },
    { value: 'hd', label: '1440×900 (HD)', width: 1440, height: 900 },
    { value: 'fullhd', label: '1920×1080 (Full HD)', width: 1920, height: 1080 },
    { value: 'custom', label: 'Свой размер', width: 1440, height: 900 },
]

export function CreateDashboardDialog() {
    const navigate = useNavigate()
    const { projectId } = useParams()
    const { createDashboard } = useDashboardStore()
    const { createDashboardDialogOpen, closeCreateDashboardDialog, createDashboardProjectId } = useUIStore()

    const [name, setName] = useState('')
    const [preset, setPreset] = useState<CanvasPreset>('hd')
    const [customWidth, setCustomWidth] = useState(1440)
    const [customHeight, setCustomHeight] = useState(900)
    const [isCreating, setIsCreating] = useState(false)

    const effectiveProjectId = createDashboardProjectId || projectId

    const handleCreate = async () => {
        if (!name.trim() || !effectiveProjectId) return

        setIsCreating(true)
        const selectedPreset = presets.find(p => p.value === preset)
        const width = preset === 'custom' ? customWidth : (selectedPreset?.width ?? 1440)
        const height = preset === 'custom' ? customHeight : (selectedPreset?.height ?? 900)

        const dashboard = await createDashboard({
            project_id: effectiveProjectId,
            name: name.trim(),
            settings: {
                canvas_width: width,
                canvas_height: height,
                canvas_preset: preset,
            },
        })

        setIsCreating(false)
        if (dashboard) {
            setName('')
            setPreset('hd')
            closeCreateDashboardDialog()
            navigate(`/project/${effectiveProjectId}/dashboard/${dashboard.id}`)
        }
    }

    return (
        <Dialog open={createDashboardDialogOpen} onOpenChange={(open) => !open && closeCreateDashboardDialog()}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Новый дашборд</DialogTitle>
                    <DialogDescription>
                        Создайте дашборд для презентации ваших данных
                    </DialogDescription>
                </DialogHeader>

                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="dashboard-name">Название</Label>
                        <Input
                            id="dashboard-name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Мой дашборд"
                            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                            autoFocus
                        />
                    </div>

                    <div className="grid gap-2">
                        <Label>Размер холста</Label>
                        <div className="grid grid-cols-2 gap-2">
                            {presets.map((p) => (
                                <button
                                    key={p.value}
                                    onClick={() => setPreset(p.value)}
                                    className={`text-left px-3 py-2 rounded-md border text-sm transition-colors ${preset === p.value
                                        ? 'border-primary bg-primary/10 text-primary'
                                        : 'border-border hover:bg-muted/50'
                                        }`}
                                >
                                    {p.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {preset === 'custom' && (
                        <div className="grid grid-cols-2 gap-4">
                            <div className="grid gap-2">
                                <Label htmlFor="custom-width">Ширина (px)</Label>
                                <Input
                                    id="custom-width"
                                    type="number"
                                    value={customWidth}
                                    onChange={(e) => setCustomWidth(Number(e.target.value))}
                                    min={800}
                                    max={3840}
                                />
                            </div>
                            <div className="grid gap-2">
                                <Label htmlFor="custom-height">Высота (px)</Label>
                                <Input
                                    id="custom-height"
                                    type="number"
                                    value={customHeight}
                                    onChange={(e) => setCustomHeight(Number(e.target.value))}
                                    min={400}
                                    max={2160}
                                />
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={closeCreateDashboardDialog}>
                        Отмена
                    </Button>
                    <Button onClick={handleCreate} disabled={!name.trim() || isCreating}>
                        {isCreating ? 'Создание...' : 'Создать'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
