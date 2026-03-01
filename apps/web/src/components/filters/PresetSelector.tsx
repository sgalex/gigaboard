/**
 * PresetSelector — list of filter presets with apply/delete actions.
 * See docs/CROSS_FILTER_SYSTEM.md §6 (Phase 6.4)
 */
import { useState } from 'react'
import { Star, Trash2, Play, Plus, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useFilterStore } from '@/store/filterStore'

export function PresetSelector() {
    const presets = useFilterStore((s) => s.presets)
    const activePresetId = useFilterStore((s) => s.activePresetId)
    const activeFilters = useFilterStore((s) => s.activeFilters)
    const applyPreset = useFilterStore((s) => s.applyPreset)
    const saveAsPreset = useFilterStore((s) => s.saveAsPreset)
    const context = useFilterStore((s) => s.context)
    const loadPresets = useFilterStore((s) => s.loadPresets)

    const [isSaving, setIsSaving] = useState(false)
    const [newName, setNewName] = useState('')

    const handleSave = async () => {
        if (!newName.trim()) return
        setIsSaving(true)
        try {
            await saveAsPreset(newName.trim())
            setNewName('')
        } finally {
            setIsSaving(false)
        }
    }

    const handleDelete = async (presetId: string) => {
        if (!context) return
        try {
            const { filterPresetsAPI } = await import('@/services/api')
            await filterPresetsAPI.delete(context.projectId, presetId)
            await loadPresets(context.projectId)
        } catch (e) {
            console.error('Failed to delete preset', e)
        }
    }

    return (
        <div className="flex flex-col gap-3">
            <h4 className="text-sm font-medium">Пресеты фильтров</h4>

            {presets.length === 0 && (
                <p className="text-xs text-muted-foreground">Нет сохранённых пресетов</p>
            )}

            <div className="flex flex-col gap-1.5">
                {presets.map((p) => (
                    <div
                        key={p.id}
                        className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs border transition-colors ${p.id === activePresetId
                                ? 'border-primary/40 bg-primary/5'
                                : 'border-transparent hover:bg-muted/50'
                            }`}
                    >
                        {p.is_default && <Star className="h-3 w-3 text-amber-500 flex-shrink-0" />}
                        <span className="flex-1 truncate">{p.name}</span>
                        {p.description && (
                            <span className="text-[10px] text-muted-foreground truncate max-w-[100px]">
                                {p.description}
                            </span>
                        )}
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 flex-shrink-0"
                            onClick={() => applyPreset(p.id)}
                            title="Применить"
                        >
                            <Play className="h-3 w-3" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 flex-shrink-0 text-destructive"
                            onClick={() => handleDelete(p.id)}
                            title="Удалить"
                        >
                            <Trash2 className="h-3 w-3" />
                        </Button>
                    </div>
                ))}
            </div>

            {/* Save current as preset */}
            {activeFilters && (
                <div className="flex items-center gap-1.5 pt-2 border-t">
                    <Input
                        className="h-7 text-xs flex-1"
                        placeholder="Название пресета"
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                    />
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs gap-1 flex-shrink-0"
                        onClick={handleSave}
                        disabled={!newName.trim() || isSaving}
                    >
                        <Save className="h-3 w-3" />
                        Сохранить
                    </Button>
                </div>
            )}
        </div>
    )
}
