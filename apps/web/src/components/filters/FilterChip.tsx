/**
 * FilterChip — displays a single active filter condition as a removable chip.
 * See docs/CROSS_FILTER_SYSTEM.md §7.3
 */
import { X, Globe, DollarSign, Calendar, ToggleLeft, Hash } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { FilterCondition, DimensionType } from '@/types/crossFilter'
import { operatorLabel } from '@/types/crossFilter'
import type { Dimension } from '@/types/crossFilter'

// ── Dimension type icons ──────────────────────────────────────────

const DIM_TYPE_ICONS: Record<DimensionType, typeof Globe> = {
    string: Globe,
    number: DollarSign,
    date: Calendar,
    boolean: ToggleLeft,
}

function getDimIcon(dimType?: DimensionType) {
    if (!dimType) return Hash
    return DIM_TYPE_ICONS[dimType] || Hash
}

// ── Format display value ──────────────────────────────────────────

function formatValue(value: FilterCondition['value']): string {
    if (value === null || value === undefined) return '—'
    if (Array.isArray(value)) {
        if (value.length === 2 && typeof value[0] === 'number' && typeof value[1] === 'number') {
            return `${value[0]}..${value[1]}`
        }
        return value.join(', ')
    }
    if (typeof value === 'boolean') return value ? 'Да' : 'Нет'
    return String(value)
}

// ── Props ─────────────────────────────────────────────────────────

interface FilterChipProps {
    condition: FilterCondition
    dimension?: Dimension | null
    onRemove: (dimName: string) => void
    onClick?: (condition: FilterCondition) => void
}

export function FilterChip({ condition, dimension, onRemove, onClick }: FilterChipProps) {
    const Icon = getDimIcon(dimension?.dim_type)
    const displayName = dimension?.display_name || condition.dim
    const opStr = operatorLabel(condition.op)
    const valStr = formatValue(condition.value)

    return (
        <Badge
            variant="secondary"
            className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 cursor-pointer hover:bg-secondary/80 transition-colors max-w-[240px]"
            onClick={() => onClick?.(condition)}
        >
            <Icon className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
            <span className="text-xs font-medium truncate">{displayName}</span>
            <span className="text-xs text-muted-foreground">{opStr}</span>
            <span className="text-xs font-medium truncate max-w-[100px]">{valStr}</span>
            <Button
                variant="ghost"
                size="icon"
                className="h-4 w-4 ml-0.5 hover:bg-destructive/20 rounded-full flex-shrink-0"
                onClick={(e) => {
                    e.stopPropagation()
                    onRemove(condition.dim)
                }}
            >
                <X className="h-2.5 w-2.5" />
            </Button>
        </Badge>
    )
}
