/**
 * FilterConditionRow — single condition line inside FilterBuilder.
 * Dimension dropdown → Operator dropdown → Value input → Remove button.
 * See docs/CROSS_FILTER_SYSTEM.md §6 (Phase 6.3)
 */
import { useState, useRef, useEffect } from 'react'
import { X, Search, ChevronDown, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import type {
    FilterCondition,
    FilterOperator,
    DimensionType,
    Dimension,
} from '@/types/crossFilter'
import { operatorLabel } from '@/types/crossFilter'

// ── Operators by dimension type ───────────────────────────────────

const OPERATORS_BY_TYPE: Record<DimensionType, FilterOperator[]> = {
    string: ['==', '!=', 'in', 'not_in', 'contains', 'starts_with'],
    number: ['==', '!=', '>', '<', '>=', '<=', 'between', 'in'],
    date: ['==', '!=', '>', '<', '>=', '<=', 'between'],
    boolean: ['==', '!='],
}

const ALL_OPERATORS: FilterOperator[] = [
    '==', '!=', '>', '<', '>=', '<=', 'in', 'not_in', 'between', 'contains', 'starts_with',
]

// ── Props ─────────────────────────────────────────────────────────

interface FilterConditionRowProps {
    condition: FilterCondition
    dimensions: Dimension[]
    onChange: (updated: FilterCondition) => void
    onRemove: () => void
}

export function FilterConditionRow({
    condition,
    dimensions,
    onChange,
    onRemove,
}: FilterConditionRowProps) {
    const currentDim = dimensions.find((d) => d.name === condition.dim)
    const availableOps = currentDim
        ? OPERATORS_BY_TYPE[currentDim.dim_type] || ALL_OPERATORS
        : ALL_OPERATORS

    const [rawValue, setRawValue] = useState(
        condition.value != null ? String(condition.value) : ''
    )

    const handleDimChange = (dimName: string) => {
        const dim = dimensions.find((d) => d.name === dimName)
        // Reset operator and value when dimension changes
        const defaultOp = dim ? (OPERATORS_BY_TYPE[dim.dim_type]?.[0] || '==') : '=='
        onChange({
            ...condition,
            dim: dimName,
            op: defaultOp,
            value: null,
        })
        setRawValue('')
    }

    const handleOpChange = (op: string) => {
        onChange({ ...condition, op: op as FilterOperator })
    }

    const handleValueCommit = () => {
        let parsed: FilterCondition['value'] = rawValue

        if (currentDim?.dim_type === 'number') {
            const num = Number(rawValue)
            parsed = isNaN(num) ? rawValue : num
        } else if (currentDim?.dim_type === 'boolean') {
            parsed = rawValue.toLowerCase() === 'true' || rawValue === '1'
        } else if (condition.op === 'in' || condition.op === 'not_in') {
            parsed = rawValue.split(',').map((s) => s.trim()).filter(Boolean)
        } else if (condition.op === 'between') {
            const parts = rawValue.split(',').map((s) => s.trim())
            if (parts.length === 2) {
                parsed = [Number(parts[0]) || 0, Number(parts[1]) || 0] as [number, number]
            }
        }

        onChange({ ...condition, value: parsed })
    }

    const knownValues = currentDim?.known_values?.values
    const useSearchableDropdown = knownValues && knownValues.length > 0 && (condition.op === '==' || condition.op === '!=')

    return (
        <div className="flex items-center gap-1.5 group">
            {/* Dimension selector */}
            <Select value={condition.dim} onValueChange={handleDimChange}>
                <SelectTrigger className="h-8 text-xs w-[140px] flex-shrink-0">
                    <SelectValue placeholder="Измерение" />
                </SelectTrigger>
                <SelectContent>
                    {dimensions.map((d) => (
                        <SelectItem key={d.id} value={d.name} className="text-xs">
                            {d.display_name}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>

            {/* Operator */}
            <Select value={condition.op} onValueChange={handleOpChange}>
                <SelectTrigger className="h-8 text-xs w-[100px] flex-shrink-0">
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {availableOps.map((op) => (
                        <SelectItem key={op} value={op} className="text-xs">
                            {operatorLabel(op)}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>

            {/* Value */}
            {useSearchableDropdown ? (
                <SearchableValueSelect
                    values={knownValues}
                    selected={rawValue}
                    onSelect={(v) => {
                        setRawValue(v)
                        onChange({ ...condition, value: currentDim?.dim_type === 'number' ? Number(v) : v })
                    }}
                />
            ) : (
                <Input
                    className="h-8 text-xs w-[140px]"
                    placeholder={
                        condition.op === 'between'
                            ? 'от, до'
                            : condition.op === 'in' || condition.op === 'not_in'
                                ? 'a, b, c'
                                : 'Значение'
                    }
                    value={rawValue}
                    onChange={(e) => setRawValue(e.target.value)}
                    onBlur={handleValueCommit}
                    onKeyDown={(e) => e.key === 'Enter' && handleValueCommit()}
                />
            )}

            {/* Remove */}
            <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                onClick={onRemove}
            >
                <X className="h-3.5 w-3.5 text-destructive" />
            </Button>
        </div>
    )
}

// ── Searchable value dropdown ─────────────────────────────────────

function SearchableValueSelect({
    values,
    selected,
    onSelect,
}: {
    values: any[]
    selected: string
    onSelect: (v: string) => void
}) {
    const [open, setOpen] = useState(false)
    const [search, setSearch] = useState('')
    const containerRef = useRef<HTMLDivElement>(null)
    const searchInputRef = useRef<HTMLInputElement>(null)

    useEffect(() => {
        if (open && searchInputRef.current) {
            searchInputRef.current.focus()
        }
    }, [open])

    useEffect(() => {
        if (!open) return
        const handler = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setOpen(false)
                setSearch('')
            }
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [open])

    const filtered = values
        .map((v) => String(v))
        .filter((v) => !search || v.toLowerCase().includes(search.toLowerCase()))

    return (
        <div ref={containerRef} className="relative w-[140px]">
            <button
                type="button"
                onClick={() => setOpen(!open)}
                className="flex items-center justify-between w-full h-8 px-2 text-xs border rounded-md bg-background hover:bg-accent/50 transition-colors"
            >
                <span className="truncate text-left flex-1">
                    {selected || <span className="text-muted-foreground">Значение</span>}
                </span>
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0 ml-1" />
            </button>

            {open && (
                <div className="absolute top-[calc(100%+4px)] left-0 w-[220px] bg-popover border rounded-md shadow-lg z-50 overflow-hidden">
                    <div className="flex items-center gap-1.5 px-2 py-1.5 border-b">
                        <Search className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                        <input
                            ref={searchInputRef}
                            type="text"
                            className="flex-1 text-xs bg-transparent outline-none placeholder:text-muted-foreground"
                            placeholder="Поиск..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                    <div className="max-h-[200px] overflow-y-auto">
                        {filtered.length === 0 ? (
                            <div className="px-2 py-3 text-xs text-muted-foreground text-center">
                                Ничего не найдено
                            </div>
                        ) : (
                            filtered.map((v) => (
                                <button
                                    key={v}
                                    type="button"
                                    className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-left hover:bg-accent/50 transition-colors"
                                    onClick={() => {
                                        onSelect(v)
                                        setOpen(false)
                                        setSearch('')
                                    }}
                                >
                                    <Check className={`h-3 w-3 flex-shrink-0 ${v === selected ? 'opacity-100' : 'opacity-0'}`} />
                                    <span className="truncate">{v}</span>
                                </button>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
