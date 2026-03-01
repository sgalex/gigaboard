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
    contentClassName?: string  // For custom content area styles
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
    contentClassName,
}: BaseSourceDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className={`${className} max-h-[calc(100vh-2rem)] flex flex-col overflow-hidden p-4 gap-2`}>
                <DialogHeader className="space-y-0.5">
                    <DialogTitle className="flex items-center gap-2 text-sm">
                        {icon}
                        {title}
                    </DialogTitle>
                    {description && (
                        <DialogDescription className="text-xs">{description}</DialogDescription>
                    )}
                </DialogHeader>

                <div className={`min-h-0 flex-1 flex flex-col py-1 ${contentClassName || 'overflow-y-auto'}`}>
                    {children}
                </div>

                <DialogFooter className="pt-1">
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        disabled={isLoading}
                    >
                        Отмена
                    </Button>
                    <Button
                        size="sm"
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
