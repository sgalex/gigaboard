/**
 * FilterStats — shows filtering statistics per table.
 * See docs/CROSS_FILTER_SYSTEM.md §7.4 (Section C)
 */
import { BarChart3 } from 'lucide-react'
import { useFilterStore } from '@/store/filterStore'

export function FilterStats() {
    const filterStats = useFilterStore((s) => s.filterStats)
    const activeFilters = useFilterStore((s) => s.activeFilters)

    if (!activeFilters || filterStats.length === 0) {
        return (
            <div className="flex flex-col gap-2">
                <h4 className="text-sm font-medium flex items-center gap-1.5">
                    <BarChart3 className="h-3.5 w-3.5" />
                    Статистика
                </h4>
                <p className="text-xs text-muted-foreground">
                    {activeFilters ? 'Статистика загружается...' : 'Нет активных фильтров'}
                </p>
            </div>
        )
    }

    return (
        <div className="flex flex-col gap-2">
            <h4 className="text-sm font-medium flex items-center gap-1.5">
                <BarChart3 className="h-3.5 w-3.5" />
                Статистика фильтрации
            </h4>

            <div className="flex flex-col gap-1.5">
                {filterStats.map((stat) => (
                    <div key={stat.table_name} className="flex flex-col gap-1">
                        <div className="flex items-center justify-between text-xs">
                            <span className="font-medium truncate">{stat.table_name}</span>
                            <span className="text-muted-foreground flex-shrink-0">
                                {stat.filtered_rows} / {stat.total_rows}
                            </span>
                        </div>
                        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                                className="h-full bg-primary rounded-full transition-all duration-300"
                                style={{ width: `${Math.min(100, stat.percentage)}%` }}
                            />
                        </div>
                        <span className="text-[10px] text-muted-foreground">
                            {stat.percentage.toFixed(1)}% строк
                        </span>
                    </div>
                ))}
            </div>
        </div>
    )
}
