import { X, CheckCircle2, AlertCircle, Info } from 'lucide-react'
import { useEffect } from 'react'
import { useNotificationStore, type NotificationToast } from '@/store/notificationStore'
import { cn } from '@/lib/utils'

function ToastIcon({ type }: { type: NotificationToast['type'] }) {
    if (type === 'success') return <CheckCircle2 className="h-4 w-4 text-emerald-500" />
    if (type === 'error') return <AlertCircle className="h-4 w-4 text-destructive" />
    return <Info className="h-4 w-4 text-sky-500" />
}

function ToastItem({ toast }: { toast: NotificationToast }) {
    const dismiss = useNotificationStore((s) => s.dismiss)

    useEffect(() => {
        const timeout = window.setTimeout(() => dismiss(toast.id), toast.durationMs)
        return () => window.clearTimeout(timeout)
    }, [dismiss, toast.durationMs, toast.id])

    return (
        <div
            role="status"
            className={cn(
                'pointer-events-auto w-[360px] rounded-xl border bg-background/95 backdrop-blur p-4 shadow-xl',
                toast.type === 'error' && 'border-destructive/30',
                toast.type === 'success' && 'border-emerald-500/20',
                toast.type === 'info' && 'border-sky-500/20'
            )}
        >
            <div className="flex items-start gap-3">
                <div className="mt-0.5">
                    <ToastIcon type={toast.type} />
                </div>

                <div className="min-w-0 flex-1">
                    {toast.title && (
                        <div className="text-sm font-semibold text-foreground">{toast.title}</div>
                    )}
                    <div className="text-sm text-muted-foreground break-words">{toast.message}</div>
                </div>

                <button
                    type="button"
                    aria-label="Закрыть уведомление"
                    onClick={() => dismiss(toast.id)}
                    className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent"
                >
                    <X className="h-4 w-4" />
                </button>
            </div>
        </div>
    )
}

export function Toaster() {
    const toasts = useNotificationStore((s) => s.toasts)

    if (toasts.length === 0) return null

    return (
        <div className="pointer-events-none fixed right-4 top-4 z-50 flex flex-col gap-3">
            {toasts.map((t) => (
                <ToastItem key={t.id} toast={t} />
            ))}
        </div>
    )
}
