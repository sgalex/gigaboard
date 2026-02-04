/**
 * Stream Source Dialog - заглушка для Phase 4.
 */
import { Radio } from 'lucide-react'
import { BaseSourceDialog } from './BaseSourceDialog'
import { SourceDialogProps } from './types'

export function StreamSourceDialog({ open, onOpenChange }: SourceDialogProps) {
    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Стрим (Real-time)"
            description="Подключение к real-time потокам данных"
            icon={<Radio className="h-5 w-5 text-cyan-500" />}
            isLoading={false}
            isValid={false}
            onSubmit={() => { }}
        >
            <div className="flex flex-col items-center justify-center py-12 text-center">
                <Radio className="h-16 w-16 text-muted-foreground/30 mb-4" />
                <h3 className="text-lg font-medium mb-2">Скоро будет доступно</h3>
                <p className="text-sm text-muted-foreground max-w-sm">
                    Поддержка real-time стримов (WebSocket, SSE, Apache Kafka)
                    будет добавлена в Phase 4.
                </p>
            </div>
        </BaseSourceDialog>
    )
}
