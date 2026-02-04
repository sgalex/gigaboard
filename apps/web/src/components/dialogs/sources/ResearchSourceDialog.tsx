/**
 * Research Source Dialog - AI Deep Research через мультиагентов.
 */
import { useState } from 'react'
import { Search } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'

export function ResearchSourceDialog({ open, onOpenChange, initialPosition }: SourceDialogProps) {
    const [prompt, setPrompt] = useState('')

    const { isLoading, create } = useSourceDialog({
        sourceType: SourceType.RESEARCH,
        onClose: () => {
            setPrompt('')
            onOpenChange(false)
        },
        position: initialPosition,
    })

    const handleSubmit = async () => {
        if (!prompt.trim()) {
            notify.error('Введите запрос для исследования')
            return
        }

        await create({
            initial_prompt: prompt.trim(),
            context: {},
        }, {
            name: prompt.slice(0, 50) + (prompt.length > 50 ? '...' : ''),
        })
    }

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title="AI Research"
            description="AI-агенты найдут и структурируют данные из открытых источников"
            icon={<Search className="h-5 w-5 text-pink-500" />}
            isLoading={isLoading}
            isValid={prompt.trim().length > 0}
            onSubmit={handleSubmit}
            submitLabel="Начать исследование"
        >
            <div className="space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="research-prompt">Запрос для исследования *</Label>
                    <Textarea
                        id="research-prompt"
                        placeholder="Опишите, какие данные нужно найти и как их структурировать...

Например:
• Найди статистику продаж электромобилей по странам за 2024-2025
• Собери информацию о топ-10 стартапах в сфере AI за последний год
• Составь таблицу сравнения характеристик популярных смартфонов"
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        rows={6}
                    />
                </div>

                <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
                    <p className="font-medium mb-2">Как это работает:</p>
                    <ol className="list-decimal list-inside space-y-1">
                        <li><strong>SearchAgent</strong> — ищет релевантные источники</li>
                        <li><strong>ResearcherAgent</strong> — анализирует найденные данные</li>
                        <li><strong>AnalystAgent</strong> — структурирует в таблицу</li>
                    </ol>
                    <p className="mt-3 text-xs">
                        ⚠️ Исследование может занять несколько минут
                    </p>
                </div>
            </div>
        </BaseSourceDialog>
    )
}
