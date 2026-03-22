import { Loader2, CheckCircle2, Circle, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ProgressMeta, ProgressStep } from '@/lib/multiAgentProgress'

type ProgressVariant = 'blue' | 'purple' | 'primary'

interface MultiAgentProgressBlockProps {
    runningText: string
    progressMeta: ProgressMeta
    progressSteps: ProgressStep[]
    variant?: ProgressVariant
    emptyText?: string
}

function getVariantClasses(variant: ProgressVariant) {
    if (variant === 'blue') {
        return {
            bar: 'bg-blue-500',
            runningBorder: 'border-blue-500/50',
            runningBg: 'bg-blue-500/5',
            runningIcon: 'text-blue-500',
        }
    }
    if (variant === 'purple') {
        return {
            bar: 'bg-purple-500',
            runningBorder: 'border-purple-500/50',
            runningBg: 'bg-purple-500/5',
            runningIcon: 'text-purple-500',
        }
    }
    return {
        bar: 'bg-primary',
        runningBorder: 'border-primary/50',
        runningBg: 'bg-primary/5',
        runningIcon: 'text-primary',
    }
}

export function MultiAgentProgressBlock({
    runningText,
    progressMeta,
    progressSteps,
    variant = 'primary',
    emptyText = 'Ожидание первого шага...',
}: MultiAgentProgressBlockProps) {
    const v = getVariantClasses(variant)

    return (
        <div className="rounded-md px-2 py-1.5 text-xs bg-muted text-foreground">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {runningText}
            </div>
            <div className="mb-1.5">
                <div className="h-1.5 w-full rounded-full bg-background/80 overflow-hidden border border-border/60">
                    <div
                        className={cn('h-full transition-all duration-300', v.bar, progressMeta.total == null && 'animate-pulse w-1/3')}
                        style={
                            progressMeta.total != null
                                ? {
                                      width: `${Math.max(
                                          4,
                                          Math.min(
                                              100,
                                              Math.round(
                                                  (progressMeta.current / Math.max(progressMeta.total, 1)) * 100
                                              )
                                          )
                                      )}%`,
                                  }
                                : undefined
                        }
                    />
                </div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                    {progressMeta.total != null
                        ? `Прогресс: шаг ${Math.min(progressMeta.current, progressMeta.total)} из ${progressMeta.total}`
                        : 'Прогресс: выполняю шаги пайплайна...'}
                </div>
            </div>
            {progressSteps.length > 0 ? (
                <div className="space-y-1 mt-1">
                    {progressSteps.map((step) => (
                        <div
                            key={step.id}
                            className={cn(
                                'rounded border px-1.5 py-1',
                                step.status === 'running' && cn(v.runningBorder, v.runningBg),
                                step.status === 'completed' && 'border-border bg-background/60',
                                step.status === 'failed' && 'border-destructive/40 bg-destructive/5',
                                step.status === 'pending' && 'border-border/70 bg-background/30'
                            )}
                        >
                            <div className="flex items-start gap-1.5">
                                <div className="mt-0.5 shrink-0">
                                    {step.status === 'running' ? (
                                        <Loader2 className={cn('w-3 h-3 animate-spin', v.runningIcon)} />
                                    ) : step.status === 'completed' ? (
                                        <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                                    ) : step.status === 'failed' ? (
                                        <AlertCircle className="w-3 h-3 text-destructive" />
                                    ) : (
                                        <Circle className="w-3 h-3 text-muted-foreground" />
                                    )}
                                </div>
                                <div className="text-[11px] leading-tight text-muted-foreground break-words">
                                    {step.text}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-xs text-muted-foreground">{emptyText}</p>
            )}
        </div>
    )
}

