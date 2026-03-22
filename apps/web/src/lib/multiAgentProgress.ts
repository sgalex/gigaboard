export type ProgressStepStatus = 'pending' | 'running' | 'completed' | 'failed'

export type ProgressStep = {
    id: string
    text: string
    status: ProgressStepStatus
}

export type ProgressMeta = {
    current: number
    total: number | null
}

export function normalizeProgressText(value: unknown): string {
    return String(value || '').trim()
}

export function mergePlanSteps(
    prevSteps: ProgressStep[],
    incomingStepsRaw: string[],
    completedCountRaw: number | undefined,
    idPrefix: string
): ProgressStep[] {
    const incomingSteps = incomingStepsRaw
        .map((s) => normalizeProgressText(s))
        .filter((s) => s.length > 0)
    if (incomingSteps.length === 0) return prevSteps

    const prevRunningTexts = prevSteps
        .filter((s) => s.status === 'running')
        .map((s) => normalizeProgressText(s.text))
        .filter((s) => s.length > 0)

    const preservedDone = prevSteps.filter((s) => s.status === 'completed' || s.status === 'failed')
    const preservedTexts = new Set(preservedDone.map((s) => normalizeProgressText(s.text)))

    const completedCount = Math.max(0, Math.min(Number(completedCountRaw || 0), incomingSteps.length))
    const tailFromServer = incomingSteps.slice(completedCount)
    const mergedTail = tailFromServer.filter((text) => !preservedTexts.has(text))

    let nextSteps: ProgressStep[] = [
        ...preservedDone,
        ...mergedTail.map((stepText, idx) => ({
            id: `${idPrefix}-plan-tail-${idx}-${Math.random().toString(36).slice(2, 6)}`,
            text: stepText,
            status: 'pending' as const,
        })),
    ]

    let runningIdx = nextSteps.findIndex(
        (step) =>
            step.status === 'pending' &&
            prevRunningTexts.includes(normalizeProgressText(step.text))
    )
    if (runningIdx < 0) {
        runningIdx = nextSteps.findIndex((step) => step.status === 'pending')
    }
    if (runningIdx >= 0) {
        nextSteps = nextSteps.map((step, idx) =>
            idx === runningIdx ? { ...step, status: 'running' as const } : step
        )
    }
    return nextSteps
}

export function applyProgressToSteps(
    prevSteps: ProgressStep[],
    task: string,
    stepIndexRaw: number | undefined,
    idPrefix: string
): ProgressStep[] {
    const stepIndex =
        typeof stepIndexRaw === 'number' && stepIndexRaw > 0 ? Math.floor(stepIndexRaw) : null
    const taskText = normalizeProgressText(task)
    let nextSteps = prevSteps

    const matchedIdx =
        taskText.length > 0
            ? nextSteps.findIndex(
                  (step) =>
                      normalizeProgressText(step.text) === taskText &&
                      step.status !== 'completed' &&
                      step.status !== 'failed'
              )
            : -1

    if (matchedIdx >= 0) {
        return nextSteps.map((step, idx) => {
            if (step.status === 'failed') return step
            if (idx < matchedIdx) {
                return step.status === 'completed' ? step : { ...step, status: 'completed' as const }
            }
            if (idx === matchedIdx) {
                return { ...step, status: 'running' as const }
            }
            return step.status === 'completed' ? step : { ...step, status: 'pending' as const }
        })
    }

    if (stepIndex != null && nextSteps.length >= stepIndex) {
        const runningIdx = Math.max(0, stepIndex - 1)
        return nextSteps.map((step, idx) => ({
            ...step,
            status:
                step.status === 'failed'
                    ? 'failed'
                    : step.status === 'completed'
                    ? 'completed'
                    : idx < runningIdx
                    ? 'completed'
                    : idx === runningIdx
                    ? 'running'
                    : 'pending',
        }))
    }

    const fallbackText = taskText || 'Выполняю шаг'
    const existingIdx = nextSteps.findIndex(
        (step) =>
            normalizeProgressText(step.text) === fallbackText &&
            step.status !== 'completed' &&
            step.status !== 'failed'
    )
    if (existingIdx >= 0) {
        return nextSteps.map((step, idx) => ({
            ...step,
            status:
                step.status === 'failed'
                    ? 'failed'
                    : step.status === 'completed'
                    ? 'completed'
                    : idx < existingIdx
                    ? 'completed'
                    : idx === existingIdx
                    ? 'running'
                    : 'pending',
        }))
    }

    return [
        ...nextSteps.map((step) =>
            step.status === 'running' ? { ...step, status: 'completed' as const } : step
        ),
        {
            id: `${idPrefix}-step-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            text: fallbackText,
            status: 'running',
        },
    ]
}

export function markRunningAsCompleted(steps: ProgressStep[]): ProgressStep[] {
    return steps.map((step) => (step.status === 'running' ? { ...step, status: 'completed' } : step))
}

export function markLastRunningAsFailed(steps: ProgressStep[]): ProgressStep[] {
    const runningIndexes = steps
        .map((s, idx) => (s.status === 'running' ? idx : -1))
        .filter((idx) => idx >= 0)
    if (runningIndexes.length === 0) return steps
    const lastRunningIdx = runningIndexes[runningIndexes.length - 1]
    return steps.map((step, idx) =>
        idx === lastRunningIdx ? { ...step, status: 'failed' as const } : step
    )
}

export function updateMetaFromPlanEvent(
    prevMeta: ProgressMeta,
    totalStepsRaw: number,
    completedCountRaw: number | undefined
): ProgressMeta {
    const total = totalStepsRaw > 0 ? totalStepsRaw : prevMeta.total
    return {
        current: Math.max(0, Number(completedCountRaw || 0)),
        total,
    }
}

export function updateMetaFromProgressEvent(
    prevMeta: ProgressMeta,
    stepIndexRaw: number | undefined,
    totalStepsRaw: number | undefined
): ProgressMeta {
    const totalSteps =
        typeof totalStepsRaw === 'number' && totalStepsRaw > 0 ? Math.floor(totalStepsRaw) : null
    const stepIndex =
        typeof stepIndexRaw === 'number' && stepIndexRaw > 0 ? Math.floor(stepIndexRaw) : null
    const nextTotal = totalSteps != null ? Math.max(prevMeta.total ?? 0, totalSteps) : prevMeta.total
    if (stepIndex != null) {
        return {
            current: nextTotal != null ? Math.min(stepIndex, nextTotal) : stepIndex,
            total: nextTotal ?? null,
        }
    }
    return {
        current: nextTotal != null ? Math.min(prevMeta.current + 1, nextTotal) : prevMeta.current + 1,
        total: nextTotal ?? null,
    }
}

export function finalizeMeta(prevMeta: ProgressMeta, fallbackLength: number): ProgressMeta {
    const resolvedTotal = prevMeta.total ?? (prevMeta.current > 0 ? prevMeta.current : null)
    return {
        current: resolvedTotal ?? Math.max(prevMeta.current, fallbackLength),
        total: resolvedTotal,
    }
}
