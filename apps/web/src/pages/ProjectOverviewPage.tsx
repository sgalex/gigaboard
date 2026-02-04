import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Plus, Calendar, Trash2, MoreVertical } from 'lucide-react'
import { AppLayout } from '@/components/layout/AppLayout'
import { ProjectExplorer } from '@/components/ProjectExplorer'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useProjectStore } from '@/store/projectStore'
import { useBoardStore } from '@/store/boardStore'
import { useUIStore } from '@/store/uiStore'
import type { BoardWithNodes } from '@/types'

export function ProjectOverviewPage() {
    const { projectId } = useParams<{ projectId: string }>()
    const navigate = useNavigate()
    const { currentProject, fetchProject } = useProjectStore()
    const { boards, fetchBoards, deleteBoard, isLoading } = useBoardStore()
    const { openCreateBoardDialog } = useUIStore()
    const [boardToDelete, setBoardToDelete] = useState<BoardWithNodes | null>(null)
    const [isDeleting, setIsDeleting] = useState(false)

    useEffect(() => {
        if (projectId) {
            fetchProject(projectId)
            fetchBoards(projectId)
        }
    }, [projectId, fetchProject, fetchBoards])

    const handleBoardClick = (boardId: string) => {
        navigate(`/project/${projectId}/board/${boardId}`)
    }

    const handleDeleteBoard = async () => {
        if (!boardToDelete) return

        setIsDeleting(true)
        try {
            await deleteBoard(boardToDelete.id)
            if (projectId) {
                await fetchBoards(projectId)
            }
        } catch (error) {
            console.error('Failed to delete board:', error)
        } finally {
            setIsDeleting(false)
            setBoardToDelete(null)
        }
    }

    if (!currentProject) {
        return (
            <AppLayout sidebar={<ProjectExplorer />}>
                <div className="h-full flex items-center justify-center">
                    <p className="text-muted-foreground">Загрузка...</p>
                </div>
            </AppLayout>
        )
    }

    return (
        <AppLayout sidebar={<ProjectExplorer />}>
            <div className="h-full overflow-y-auto bg-background p-8">
                <div className="max-w-7xl mx-auto">
                    {/* Project Header */}
                    <div className="mb-8">
                        <h1 className="text-3xl font-bold text-foreground mb-2">{currentProject.name}</h1>
                        {currentProject.description && (
                            <p className="text-muted-foreground">{currentProject.description}</p>
                        )}
                    </div>

                    {/* Quick Actions */}
                    <div className="mb-8">
                        <Button onClick={() => openCreateBoardDialog(projectId)} className="gap-2">
                            <Plus className="h-4 w-4" />
                            Создать доску
                        </Button>
                    </div>

                    {/* Boards Grid */}
                    <div>
                        <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
                            <LayoutDashboard className="h-5 w-5" />
                            Доски проекта
                        </h2>

                        {isLoading ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {[1, 2, 3].map((i) => (
                                    <Card key={i} className="animate-pulse">
                                        <CardHeader>
                                            <div className="h-6 bg-muted rounded w-3/4"></div>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="h-4 bg-muted rounded w-full"></div>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        ) : boards.length === 0 ? (
                            <Card className="border-dashed">
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <LayoutDashboard className="h-16 w-16 text-muted-foreground mb-4" />
                                    <p className="text-lg font-medium text-foreground mb-2">Нет досок</p>
                                    <p className="text-sm text-muted-foreground mb-4">
                                        Создайте первую доску для работы с данными
                                    </p>
                                    <Button onClick={() => openCreateBoardDialog(projectId)} className="gap-2">
                                        <Plus className="h-4 w-4" />
                                        Создать доску
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {boards.map((board) => (
                                    <Card
                                        key={board.id}
                                        className="hover:shadow-lg transition-shadow group relative"
                                    >
                                        <div
                                            className="cursor-pointer"
                                            onClick={() => handleBoardClick(board.id)}
                                        >
                                            <CardHeader>
                                                <CardTitle className="flex items-center justify-between gap-2 group-hover:text-primary transition-colors">
                                                    <div className="flex items-center gap-2">
                                                        <LayoutDashboard className="h-5 w-5" />
                                                        {board.name}
                                                    </div>
                                                    <DropdownMenu>
                                                        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                                            >
                                                                <MoreVertical className="h-4 w-4" />
                                                            </Button>
                                                        </DropdownMenuTrigger>
                                                        <DropdownMenuContent align="end">
                                                            <DropdownMenuItem
                                                                onClick={(e) => {
                                                                    e.stopPropagation()
                                                                    setBoardToDelete(board)
                                                                }}
                                                                className="text-destructive focus:text-destructive"
                                                            >
                                                                <Trash2 className="h-4 w-4 mr-2" />
                                                                Удалить доску
                                                            </DropdownMenuItem>
                                                        </DropdownMenuContent>
                                                    </DropdownMenu>
                                                </CardTitle>
                                                {board.description && (
                                                    <CardDescription className="line-clamp-2">{board.description}</CardDescription>
                                                )}
                                            </CardHeader>
                                            <CardContent>
                                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                                    <Calendar className="h-4 w-4" />
                                                    <span>{new Date(board.created_at).toLocaleDateString('ru-RU')}</span>
                                                </div>
                                            </CardContent>
                                            <CardFooter className="text-xs text-muted-foreground">
                                                {(board as any).data_nodes_count || 0} данных •{' '}
                                                {(board as any).widget_nodes_count || 0} виджетов •{' '}
                                                {(board as any).comment_nodes_count || 0} комментариев
                                            </CardFooter>
                                        </div>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <ConfirmDialog
                open={!!boardToDelete}
                onOpenChange={(open) => !open && setBoardToDelete(null)}
                title="Удалить доску?"
                description={`Вы уверены, что хотите удалить доску "${boardToDelete?.name}"? Все данные, виджеты и комментарии будут безвозвратно удалены. Это действие нельзя отменить.`}
                confirmText="Удалить"
                cancelText="Отмена"
                variant="danger"
                onConfirm={handleDeleteBoard}
                loading={isDeleting}
            />
        </AppLayout>
    )
}
