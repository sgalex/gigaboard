import { useState } from 'react'
import { useProjectStore } from '@/store/projectStore'
import { useUIStore } from '@/store/uiStore'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

export function CreateProjectDialog() {
    const navigate = useNavigate()
    const { createProject, isLoading } = useProjectStore()
    const { isCreateProjectDialogOpen, closeCreateProjectDialog } = useUIStore()
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        const project = await createProject({ name, description: description || undefined })

        if (project) {
            setName('')
            setDescription('')
            closeCreateProjectDialog()
            navigate(`/project/${project.id}`)
        }
    }

    const handleClose = () => {
        setName('')
        setDescription('')
        closeCreateProjectDialog()
    }

    return (
        <Dialog open={isCreateProjectDialogOpen} onOpenChange={handleClose}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Создать новый проект</DialogTitle>
                    <DialogDescription>
                        Проект — это контейнер для ваших досок, данных и аналитики
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit}>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="name">Название проекта *</Label>
                            <Input
                                id="name"
                                placeholder="Например: Анализ продаж Q1 2026"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                required
                                autoFocus
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="description">Описание (опционально)</Label>
                            <Textarea
                                id="description"
                                placeholder="Краткое описание проекта..."
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                rows={3}
                            />
                        </div>
                    </div>

                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={handleClose} disabled={isLoading}>
                            Отмена
                        </Button>
                        <Button type="submit" disabled={isLoading || !name.trim()}>
                            {isLoading ? 'Создание...' : 'Создать проект'}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
