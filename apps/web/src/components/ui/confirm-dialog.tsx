import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from '@/components/ui/alert-dialog'

export type ConfirmDialogVariant = 'danger' | 'warning' | 'info'

interface ConfirmDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    title: string
    description: string
    confirmText?: string
    cancelText?: string
    variant?: ConfirmDialogVariant
    onConfirm: () => void | Promise<void>
    loading?: boolean
}

/**
 * Универсальный компонент диалога подтверждения
 * 
 * @example
 * ```tsx
 * <ConfirmDialog
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 *   title="Удалить доску?"
 *   description="Это действие нельзя отменить. Все данные будут удалены."
 *   variant="danger"
 *   onConfirm={handleDelete}
 *   loading={isDeleting}
 * />
 * ```
 */
export function ConfirmDialog({
    open,
    onOpenChange,
    title,
    description,
    confirmText = 'Подтвердить',
    cancelText = 'Отмена',
    variant = 'info',
    onConfirm,
    loading = false,
}: ConfirmDialogProps) {
    const handleConfirm = async () => {
        await onConfirm()
        onOpenChange(false)
    }

    const getVariantStyles = () => {
        switch (variant) {
            case 'danger':
                return 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
            case 'warning':
                return 'bg-yellow-600 text-white hover:bg-yellow-700'
            case 'info':
            default:
                return ''
        }
    }

    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>{title}</AlertDialogTitle>
                    <AlertDialogDescription>{description}</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={loading}>{cancelText}</AlertDialogCancel>
                    <AlertDialogAction
                        onClick={handleConfirm}
                        disabled={loading}
                        className={getVariantStyles()}
                    >
                        {loading ? 'Выполнение...' : confirmText}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}
