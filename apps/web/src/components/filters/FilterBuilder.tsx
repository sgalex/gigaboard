/**
 * FilterBuilder — recursive AND/OR tree builder.
 * Renders FilterConditionRow for leaf conditions and nested FilterBuilder for groups.
 * See docs/CROSS_FILTER_SYSTEM.md §6 (Phase 6.2)
 */
import { Plus, FolderPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FilterConditionRow } from './FilterConditionRow'
import type {
    FilterExpression,
    FilterCondition,
    FilterGroup,
    Dimension,
} from '@/types/crossFilter'

// ── Props ─────────────────────────────────────────────────────────

interface FilterBuilderProps {
    expression: FilterExpression | null
    dimensions: Dimension[]
    onChange: (expr: FilterExpression | null) => void
    /** Depth level for visual nesting */
    depth?: number
}

// ── Helpers ───────────────────────────────────────────────────────

function makeEmptyCondition(): FilterCondition {
    return { type: 'condition', dim: '', op: '==', value: null }
}

function isGroup(expr: FilterExpression): expr is FilterGroup {
    return expr.type === 'and' || expr.type === 'or'
}

// ── Component ─────────────────────────────────────────────────────

export function FilterBuilder({
    expression,
    dimensions,
    onChange,
    depth = 0,
}: FilterBuilderProps) {
    // Normalize: wrap single condition into AND group for editing
    const group: FilterGroup = expression
        ? isGroup(expression)
            ? expression
            : { type: 'and', conditions: [expression] }
        : { type: 'and', conditions: [] }

    const groupType = group.type as 'and' | 'or'

    // Update a child at given index
    const updateChild = (index: number, child: FilterExpression | null) => {
        const next = [...group.conditions]
        if (child === null) {
            next.splice(index, 1)
        } else {
            next[index] = child
        }
        if (next.length === 0) {
            onChange(null)
        } else if (next.length === 1) {
            onChange(depth === 0 ? { ...group, conditions: next } : next[0])
        } else {
            onChange({ ...group, conditions: next })
        }
    }

    // Add new empty condition
    const addCondition = () => {
        const next: FilterGroup = {
            ...group,
            conditions: [...group.conditions, makeEmptyCondition()],
        }
        onChange(next)
    }

    // Add new nested group (AND / OR)
    const addGroup = (type: 'and' | 'or') => {
        const child: FilterGroup = {
            type,
            conditions: [makeEmptyCondition()],
        }
        const next: FilterGroup = {
            ...group,
            conditions: [...group.conditions, child],
        }
        onChange(next)
    }

    // Toggle group type (AND ↔ OR)
    const toggleGroupType = () => {
        const newType: 'and' | 'or' = groupType === 'and' ? 'or' : 'and'
        onChange({ ...group, type: newType })
    }

    const borderColor = depth === 0 ? 'border-transparent' : groupType === 'and' ? 'border-blue-300/50' : 'border-orange-300/50'
    const bgColor = depth > 0 ? (groupType === 'and' ? 'bg-blue-50/30 dark:bg-blue-950/20' : 'bg-orange-50/30 dark:bg-orange-950/20') : ''

    return (
        <div className={`flex flex-col gap-2 ${depth > 0 ? `border-l-2 ${borderColor} ${bgColor} pl-3 py-2 rounded-r` : ''}`}>
            {/* Group type label */}
            {group.conditions.length > 1 && (
                <button
                    type="button"
                    className="self-start text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded cursor-pointer hover:opacity-80 transition-opacity"
                    style={{
                        background: groupType === 'and' ? 'rgba(59,130,246,0.15)' : 'rgba(249,115,22,0.15)',
                        color: groupType === 'and' ? 'rgb(59,130,246)' : 'rgb(249,115,22)',
                    }}
                    onClick={toggleGroupType}
                    title={`Переключить на ${groupType === 'and' ? 'OR' : 'AND'}`}
                >
                    {groupType === 'and' ? 'И (AND)' : 'ИЛИ (OR)'}
                </button>
            )}

            {/* Children */}
            {group.conditions.map((child, i) => (
                <div key={i}>
                    {isGroup(child) ? (
                        <FilterBuilder
                            expression={child}
                            dimensions={dimensions}
                            onChange={(updated) => updateChild(i, updated)}
                            depth={depth + 1}
                        />
                    ) : (
                        <FilterConditionRow
                            condition={child}
                            dimensions={dimensions}
                            onChange={(updated) => updateChild(i, updated)}
                            onRemove={() => updateChild(i, null)}
                        />
                    )}
                </div>
            ))}

            {/* Add buttons */}
            <div className="flex items-center gap-1.5 mt-1">
                <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs gap-1"
                    onClick={addCondition}
                >
                    <Plus className="h-3 w-3" />
                    Условие
                </Button>
                {depth < 2 && (
                    <>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs gap-1"
                            onClick={() => addGroup('and')}
                        >
                            <FolderPlus className="h-3 w-3" />
                            Группа AND
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs gap-1"
                            onClick={() => addGroup('or')}
                        >
                            <FolderPlus className="h-3 w-3" />
                            Группа OR
                        </Button>
                    </>
                )}
            </div>
        </div>
    )
}
