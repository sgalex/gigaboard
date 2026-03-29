/** Позиционирование тултипа рекомендаций: fixed в координатах viewport */

const GAP = 8
const MARGIN = 8

export type SuggestionTooltipPlacement = 'above' | 'below'

export const SUGGESTION_TOOLTIP_WIDTH_PX = 288 // tailwind w-72

/** Быстрая оценка до измерения реальной высоты тултипа */
export function getInitialTooltipViewportPos(anchorRect: DOMRect): {
    top: number
    left: number
    placement: SuggestionTooltipPlacement
} {
    const vw = window.innerWidth
    const vh = window.innerHeight
    const estH = 260

    let left = anchorRect.left
    left = Math.max(MARGIN, Math.min(left, vw - SUGGESTION_TOOLTIP_WIDTH_PX - MARGIN))

    const spaceBelow = vh - anchorRect.bottom - MARGIN
    const spaceAbove = anchorRect.top - MARGIN

    const placeBelow =
        spaceBelow >= estH || (spaceBelow >= spaceAbove && spaceBelow >= estH * 0.45)

    const top = placeBelow
        ? anchorRect.bottom + GAP
        : Math.max(MARGIN, anchorRect.top - estH - GAP)

    return {
        top,
        left,
        placement: placeBelow ? 'below' : 'above',
    }
}

/**
 * Финальная позиция по измеренному размеру тултипа: не выходит за края окна,
 * при нехватке места снизу — над бейджем и наоборот.
 */
export function placeTooltipInViewport(
    anchorRect: DOMRect,
    tooltipWidth: number,
    tooltipHeight: number
): { top: number; left: number; placement: SuggestionTooltipPlacement } {
    const vw = window.innerWidth
    const vh = window.innerHeight
    const w = tooltipWidth
    const h = tooltipHeight

    let left = anchorRect.left
    left = Math.max(MARGIN, Math.min(left, vw - w - MARGIN))

    const belowTop = anchorRect.bottom + GAP
    const aboveTop = anchorRect.top - h - GAP

    const fitsBelow = belowTop + h <= vh - MARGIN
    const fitsAbove = aboveTop >= MARGIN

    let top: number
    let placement: SuggestionTooltipPlacement

    if (fitsBelow && fitsAbove) {
        const spaceBelow = vh - anchorRect.bottom - MARGIN
        const spaceAbove = anchorRect.top - MARGIN
        if (spaceBelow >= h + GAP || spaceBelow >= spaceAbove) {
            top = belowTop
            placement = 'below'
        } else {
            top = aboveTop
            placement = 'above'
        }
    } else if (fitsBelow) {
        top = belowTop
        placement = 'below'
    } else if (fitsAbove) {
        top = aboveTop
        placement = 'above'
    } else {
        if (anchorRect.top > vh - anchorRect.bottom) {
            top = MARGIN
            placement = 'above'
        } else {
            top = Math.max(MARGIN, vh - h - MARGIN)
            placement = 'below'
        }
    }

    top = Math.max(MARGIN, Math.min(top, vh - h - MARGIN))

    return { top, left, placement }
}

export function tooltipLayoutEqual(
    a: { top: number; left: number; placement: SuggestionTooltipPlacement },
    b: { top: number; left: number; placement: SuggestionTooltipPlacement }
): boolean {
    return (
        a.placement === b.placement &&
        Math.abs(a.top - b.top) < 0.5 &&
        Math.abs(a.left - b.left) < 0.5
    )
}
