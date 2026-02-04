import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useBoardStore } from '@/store/boardStore'
import { useProjectStore } from '@/store/projectStore'
import { useUIStore } from '@/store/uiStore'
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

export function CreateBoardDialog() {
    const { projectId } = useParams()
    const navigate = useNavigate()
    const { currentProject } = useProjectStore()
    const { createBoard, isLoading } = useBoardStore()
    const { isCreateBoardDialogOpen, closeCreateBoardDialog, contextProjectId } = useUIStore()
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')

    // Use contextProjectId from uiStore if available, otherwise fall back to route params
    const effectiveProjectId = contextProjectId || projectId

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        if (!effectiveProjectId) return

        const board = await createBoard({
            project_id: effectiveProjectId,
            name,
            description: description || undefined,
        })

        if (board) {
            setName('')
            setDescription('')
            closeCreateBoardDialog()
            navigate(`/project/${effectiveProjectId}/board/${board.id}`)
        }
    }

    const handleClose = () => {
        setName('')
        setDescription('')
        closeCreateBoardDialog()
    }

    return (
        <Dialog open={isCreateBoardDialogOpen} onOpenChange={handleClose}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Создать новую доску</DialogTitle>
                    <DialogDescription>
                        {currentProject?.name ? `В проекте: ${currentProject.name}` : 'Новая аналитическая доска'}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit}>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="board-name">Название доски *</Label>
                            <Input
                                id="board-name"
                                placeholder="Например: Dashboard продаж"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                required
                                autoFocus
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="board-description">Описание (опционально)</Label>
                            <Textarea
                                id="board-description"
                                placeholder="Краткое описание доски..."
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
                            {isLoading ? 'Создание...' : 'Создать доску'}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
