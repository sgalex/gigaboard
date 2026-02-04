/**
 * Базовый компонент диалога источника данных.
 * 
 * Предоставляет общую обёртку Dialog с заголовком и футером.
 * Используется всеми специфичными диалогами источников.
 */
import { ReactNode } from 'react'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Loader2 } from 'lucide-react'

interface BaseSourceDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    title: string
    description?: string
    icon?: ReactNode
    children: ReactNode
    isLoading?: boolean
    isValid?: boolean
    onSubmit: () => void
    submitLabel?: string
    className?: string  // For custom width
}

export function BaseSourceDialog({
    open,
    onOpenChange,
    title,
    description,
    icon,
    children,
    isLoading = false,
    isValid = true,
    onSubmit,
    submitLabel = 'Создать',
    className = 'max-w-2xl',
}: BaseSourceDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className={`${className} max-h-[90vh] overflow-y-auto`}>
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        {icon}
                        {title}
                    </DialogTitle>
                    {description && (
                        <DialogDescription>{description}</DialogDescription>
                    )}
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {children}
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        disabled={isLoading}
                    >
                        Отмена
                    </Button>
                    <Button
                        onClick={onSubmit}
                        disabled={isLoading || !isValid}
                    >
                        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {submitLabel}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
