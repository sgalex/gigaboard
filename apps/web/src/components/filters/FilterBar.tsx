/**
 * FilterBar — horizontal bar displaying active filter chips, preset selector,
 * and controls. Sits between toolbar and canvas.
 * See docs/CROSS_FILTER_SYSTEM.md §7.2
 */
import { Filter, Settings2, Trash2, ChevronDown, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { FilterChip } from './FilterChip'
import { useFilterStore } from '@/store/filterStore'
import { flattenConditions } from '@/types/crossFilter'
import type { ReactNode } from 'react'

interface FilterBarProps {
    rightActions?: ReactNode
}

export function FilterBar({ rightActions }: FilterBarProps = {}) {
    const activeFilters = useFilterStore((s) => s.activeFilters)
    const dimensions = useFilterStore((s) => s.dimensions)
    const presets = useFilterStore((s) => s.presets)
    const activePresetId = useFilterStore((s) => s.activePresetId)
    const isFilterBarVisible = useFilterStore((s) => s.isFilterBarVisible)
    const removeCondition = useFilterStore((s) => s.removeCondition)
    const clearFilters = useFilterStore((s) => s.clearFilters)
    const setFilterPanelOpen = useFilterStore((s) => s.setFilterPanelOpen)
    const applyPreset = useFilterStore((s) => s.applyPreset)

    const conditions = flattenConditions(activeFilters)
    const activePreset = presets.find((p) => p.id === activePresetId)

    // If bar is hidden or no filters and no explicit visibility — show collapsed trigger
    if (!isFilterBarVisible && conditions.length === 0) {
        return null
    }

    return (
        <div className="w-full border-b bg-background/80 backdrop-blur-sm transition-all duration-200">
            <div className="flex items-center gap-2 px-3 py-1.5 min-h-[36px]">
                {/* Filter icon + count */}
                <div className="flex items-center gap-1 text-muted-foreground flex-shrink-0">
                    <Filter className="h-3.5 w-3.5" />
                    {conditions.length > 0 && (
                        <span className="text-xs font-medium bg-primary/10 text-primary rounded-full px-1.5 min-w-[18px] text-center">
                            {conditions.length}
                        </span>
                    )}
                </div>

                {/* Filter chips */}
                <div className="flex items-center gap-1.5 flex-wrap flex-1 min-w-0">
                    {conditions.map((c) => {
                        const dim = dimensions.find((d) => d.name === c.dim)
                        return (
                            <FilterChip
                                key={c.dim}
                                condition={c}
                                dimension={dim}
                                onRemove={removeCondition}
                            />
                        )
                    })}

                    {conditions.length === 0 && (
                        <span className="text-xs text-muted-foreground">
                            Нет активных фильтров
                        </span>
                    )}
                </div>

                {/* Preset selector */}
                {presets.length > 0 && (
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm" className="h-7 text-xs gap-1 flex-shrink-0">
                                {activePreset ? activePreset.name : 'Пресеты'}
                                <ChevronDown className="h-3 w-3" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-56">
                            {presets.map((p) => (
                                <DropdownMenuItem
                                    key={p.id}
                                    onClick={() => applyPreset(p.id)}
                                    className="text-xs gap-2"
                                >
                                    {p.is_default && <span className="text-amber-500">⭐</span>}
                                    <span className="truncate">{p.name}</span>
                                    {p.id === activePresetId && (
                                        <span className="ml-auto text-primary text-[10px]">активен</span>
                                    )}
                                </DropdownMenuItem>
                            ))}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => setFilterPanelOpen(true)} className="text-xs gap-2">
                                <Plus className="h-3 w-3" />
                                Управление пресетами
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                )}

                {/* Optional host-specific actions (e.g. AI assistant in dashboard view mode) */}
                {rightActions}

                {/* Settings button — open full panel */}
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 flex-shrink-0"
                    onClick={() => setFilterPanelOpen(true)}
                    title="Настройки фильтров"
                >
                    <Settings2 className="h-3.5 w-3.5" />
                </Button>

                {/* Clear all */}
                {conditions.length > 0 && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive hover:text-destructive flex-shrink-0"
                        onClick={clearFilters}
                        title="Очистить все фильтры"
                    >
                        <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                )}
            </div>
        </div>
    )
}
