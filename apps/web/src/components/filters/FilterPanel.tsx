/**
 * FilterPanel — slide-in side panel with FilterBuilder, PresetSelector, and FilterStats.
 * Opens when user clicks ⚙ in the FilterBar.
 * See docs/CROSS_FILTER_SYSTEM.md §7.4 (Phase 6.1)
 */
import { X, SlidersHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FilterBuilder } from './FilterBuilder'
import { PresetSelector } from './PresetSelector'
import { FilterStats } from './FilterStats'
import { useFilterStore } from '@/store/filterStore'

export function FilterPanel() {
    const isOpen = useFilterStore((s) => s.isFilterPanelOpen)
    const setOpen = useFilterStore((s) => s.setFilterPanelOpen)
    const activeFilters = useFilterStore((s) => s.activeFilters)
    const dimensions = useFilterStore((s) => s.dimensions)
    const setFilters = useFilterStore((s) => s.setFilters)

    if (!isOpen) return null

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/20 z-40"
                onClick={() => setOpen(false)}
            />

            {/* Panel */}
            <div className="fixed top-0 right-0 h-full w-[400px] max-w-[90vw] bg-background border-l shadow-xl z-50 flex flex-col overflow-hidden animate-in slide-in-from-right duration-200">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b flex-shrink-0">
                    <h3 className="text-sm font-semibold flex items-center gap-2">
                        <SlidersHorizontal className="h-4 w-4" />
                        Настройки фильтров
                    </h3>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => setOpen(false)}
                    >
                        <X className="h-4 w-4" />
                    </Button>
                </div>

                {/* Scrollable content */}
                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6">
                    {/* Section A: Filter Builder */}
                    <section>
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                            Конструктор фильтров
                        </h4>
                        {dimensions.length === 0 ? (
                            <p className="text-xs text-muted-foreground">
                                Измерения не настроены. Создайте измерения в настройках проекта
                                или загрузите данные для автоматического обнаружения.
                            </p>
                        ) : (
                            <FilterBuilder
                                expression={activeFilters}
                                dimensions={dimensions}
                                onChange={setFilters}
                            />
                        )}
                    </section>

                    {/* Divider */}
                    <hr className="border-border" />

                    {/* Section B: Presets */}
                    <section>
                        <PresetSelector />
                    </section>

                    {/* Divider */}
                    <hr className="border-border" />

                    {/* Section C: Statistics */}
                    <section>
                        <FilterStats />
                    </section>
                </div>

                {/* Footer */}
                <div className="px-4 py-3 border-t flex-shrink-0 flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        onClick={() => {
                            setFilters(null)
                            setOpen(false)
                        }}
                    >
                        Сбросить все
                    </Button>
                    <div className="flex-1" />
                    <Button
                        variant="default"
                        size="sm"
                        className="text-xs"
                        onClick={() => setOpen(false)}
                    >
                        Готово
                    </Button>
                </div>
            </div>
        </>
    )
}
