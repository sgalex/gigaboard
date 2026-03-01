import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    Workflow,
    LayoutDashboard,
    Plus,
    Calendar,
    Clock,
    Trash2,
    MoreVertical,
    ArrowRight,
    Database,
    Boxes,
    BarChart3,
    Table2,
    Columns3,
    Pencil,
} from 'lucide-react'
import { AppLayout } from '@/components/layout/AppLayout'
import { ProjectExplorer } from '@/components/ProjectExplorer'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useProjectStore } from '@/store/projectStore'
import { useBoardStore } from '@/store/boardStore'
import { useDashboardStore } from '@/store/dashboardStore'
import { useUIStore } from '@/store/uiStore'
import { formatDistance } from 'date-fns'
import { ru } from 'date-fns/locale'
import type { BoardWithNodes } from '@/types'
import type { Dashboard } from '@/types/dashboard'

const DASHBOARD_STATUS_LABELS: Record<string, string> = {
    draft: 'Черновик',
    published: 'Опубликован',
    archived: 'В архиве',
}

export function ProjectOverviewPage() {
    const { projectId } = useParams<{ projectId: string }>()
    const navigate = useNavigate()
    const { currentProject, fetchProject, updateProject } = useProjectStore()
    const { boards, fetchBoards, deleteBoard, isLoading: boardsLoading } = useBoardStore()
    const { dashboards, fetchDashboards, deleteDashboard, isLoading: dashboardsLoading } = useDashboardStore()
    const { openCreateBoardDialog, openCreateDashboardDialog } = useUIStore()
    const [boardToDelete, setBoardToDelete] = useState<BoardWithNodes | null>(null)
    const [dashboardToDelete, setDashboardToDelete] = useState<Dashboard | null>(null)
    const [isDeleting, setIsDeleting] = useState(false)
    const [isEditProjectOpen, setIsEditProjectOpen] = useState(false)
    const [editName, setEditName] = useState('')
    const [editDescription, setEditDescription] = useState('')
    const [isSavingProject, setIsSavingProject] = useState(false)

    useEffect(() => {
        if (projectId) {
            fetchProject(projectId)
            fetchBoards(projectId)
            fetchDashboards(projectId)
        }
    }, [projectId, fetchProject, fetchBoards, fetchDashboards])

    const handleBoardClick = (boardId: string) => {
        navigate(`/project/${projectId}/board/${boardId}`)
    }

    const handleDashboardClick = (dashboardId: string) => {
        navigate(`/project/${projectId}/dashboard/${dashboardId}`)
    }

    const handleDeleteBoard = async () => {
        if (!boardToDelete) return
        setIsDeleting(true)
        try {
            await deleteBoard(boardToDelete.id)
            if (projectId) await fetchBoards(projectId)
        } catch (e) {
            console.error('Failed to delete board:', e)
        } finally {
            setIsDeleting(false)
            setBoardToDelete(null)
        }
    }

    const handleDeleteDashboard = async () => {
        if (!dashboardToDelete) return
        setIsDeleting(true)
        try {
            await deleteDashboard(dashboardToDelete.id)
            if (projectId) await fetchDashboards(projectId)
        } catch (e) {
            console.error('Failed to delete dashboard:', e)
        } finally {
            setIsDeleting(false)
            setDashboardToDelete(null)
        }
    }

    const openEditProject = () => {
        if (currentProject) {
            setEditName(currentProject.name)
            setEditDescription(currentProject.description ?? '')
            setIsEditProjectOpen(true)
        }
    }

    const handleSaveProject = async () => {
        if (!projectId || !editName.trim()) return
        setIsSavingProject(true)
        try {
            await updateProject(projectId, {
                name: editName.trim(),
                description: editDescription.trim() || undefined,
            })
            await fetchProject(projectId)
            setIsEditProjectOpen(false)
        } catch (e) {
            console.error('Failed to update project:', e)
        } finally {
            setIsSavingProject(false)
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
            <div className="relative min-h-full overflow-y-auto bg-transparent">
                {/* Градиент только в зоне контента проекта (не под шапкой и не под деревом) */}
                <div
                    className="absolute inset-0 z-0 overflow-hidden pointer-events-none"
                    aria-hidden
                >
                    <div
                        className="absolute inset-0"
                        style={{
                            background: `
                                radial-gradient(ellipse 85% 55% at 50% 0%, hsl(var(--primary) / 0.04), transparent 52%),
                                radial-gradient(ellipse 65% 45% at 100% 100%, hsl(var(--primary) / 0.03), transparent 55%),
                                radial-gradient(ellipse 55% 35% at 0% 85%, hsl(var(--primary) / 0.025), transparent 50%)
                            `,
                        }}
                    />
                    <div className="absolute -top-24 -right-24 h-80 w-80 rounded-full bg-primary/4 blur-3xl" />
                    <div className="absolute top-1/2 -left-24 h-96 w-96 rounded-full bg-primary/3 blur-3xl" />
                </div>

                <div className="relative z-10 max-w-6xl mx-auto px-4 py-4 sm:py-5">
                    {/* Project header */}
                    <header className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div className="min-w-0 flex items-start gap-2">
                            <div className="min-w-0 flex-1">
                                <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                                    {currentProject.name}
                                </h1>
                                {currentProject.description ? (
                                    <p className="text-sm text-muted-foreground mt-0.5 line-clamp-1">
                                        {currentProject.description}
                                    </p>
                                ) : (
                                    <p className="text-sm text-muted-foreground/60 mt-0.5 italic">Без описания</p>
                                )}
                            </div>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
                                onClick={openEditProject}
                                title="Изменить название и описание"
                            >
                                <Pencil className="h-4 w-4" />
                            </Button>
                        </div>
                        <div className="flex flex-wrap gap-2 shrink-0">
                            <Button
                                onClick={() => openCreateBoardDialog(projectId)}
                                size="sm"
                                className="gap-1.5 rounded-full shadow-sm"
                            >
                                <Workflow className="h-3.5 w-3.5" />
                                Создать доску
                            </Button>
                            <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => openCreateDashboardDialog(projectId)}
                                className="gap-1.5 rounded-full"
                            >
                                <LayoutDashboard className="h-3.5 w-3.5" />
                                Создать дашборд
                            </Button>
                        </div>
                    </header>

                    {/* Edit project dialog */}
                    <Dialog open={isEditProjectOpen} onOpenChange={setIsEditProjectOpen}>
                        <DialogContent className="sm:max-w-md">
                            <DialogHeader>
                                <DialogTitle>Редактировать проект</DialogTitle>
                            </DialogHeader>
                            <div className="grid gap-4 py-2">
                                <div className="grid gap-2">
                                    <Label htmlFor="project-name">Название</Label>
                                    <Input
                                        id="project-name"
                                        value={editName}
                                        onChange={(e) => setEditName(e.target.value)}
                                        placeholder="Название проекта"
                                        disabled={isSavingProject}
                                    />
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="project-description">Описание</Label>
                                    <Textarea
                                        id="project-description"
                                        value={editDescription}
                                        onChange={(e) => setEditDescription(e.target.value)}
                                        placeholder="Краткое описание проекта (необязательно)"
                                        rows={3}
                                        className="resize-none"
                                        disabled={isSavingProject}
                                    />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button
                                    variant="outline"
                                    onClick={() => setIsEditProjectOpen(false)}
                                    disabled={isSavingProject}
                                >
                                    Отмена
                                </Button>
                                <Button
                                    onClick={handleSaveProject}
                                    disabled={isSavingProject || !editName.trim()}
                                >
                                    {isSavingProject ? 'Сохранение...' : 'Сохранить'}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>

                    {/* Boards + Dashboards: two columns on lg, divider between */}
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_auto_1fr] lg:gap-0">
                    {/* Boards section */}
                    <section className="min-w-0 lg:pr-8">
                        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2 mb-2 sm:text-xl">
                            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                <Workflow className="h-4 w-4" />
                            </span>
                            Доски проекта
                        </h2>

                        {boardsLoading ? (
                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                {[1, 2, 3].map((i) => (
                                    <Card key={i} className="animate-pulse overflow-hidden border-0 bg-card/50 shadow-sm">
                                        <CardHeader className="p-3">
                                            <div className="h-4 bg-muted rounded-md w-3/4" />
                                            <div className="h-3 bg-muted rounded-md w-1/2 mt-2" />
                                        </CardHeader>
                                    </Card>
                                ))}
                            </div>
                        ) : boards.length === 0 ? (
                            <Card className="overflow-hidden border-dashed border-2 bg-card/30">
                                <CardContent className="flex flex-col items-center justify-center py-6">
                                    <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                        <Workflow className="h-5 w-5" />
                                    </div>
                                    <p className="text-sm font-medium text-foreground mb-1">Нет досок</p>
                                    <Button size="sm" onClick={() => openCreateBoardDialog(projectId)} className="gap-1.5 rounded-full mt-2">
                                        <Plus className="h-3.5 w-3.5" />
                                        Создать доску
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                {boards.map((board) => (
                                    <Card
                                        key={board.id}
                                        className="group relative overflow-hidden border bg-card/80 shadow-sm transition-all duration-300 hover:shadow-md hover:border-primary/20 cursor-pointer"
                                        onClick={() => handleBoardClick(board.id)}
                                    >
                                        {/* Thumbnail — создаётся/обновляется автоматически при изменении доски */}
                                        <div className="relative w-full aspect-video shrink-0 overflow-hidden bg-muted/50">
                                            {board.thumbnail_url ? (
                                                <img
                                                    src={board.thumbnail_url}
                                                    alt=""
                                                    className="h-full w-full object-cover object-top transition-transform duration-300 group-hover:scale-[1.02]"
                                                />
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-primary/5 to-primary/10">
                                                    <Workflow className="h-10 w-10 text-primary/30" aria-hidden />
                                                </div>
                                            )}
                                        </div>
                                        <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-primary/0 via-primary/30 to-primary/0 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                                        <CardHeader className="p-3 pb-1">
                                            <CardTitle className="flex items-center justify-between gap-2 text-sm font-semibold group-hover:text-primary transition-colors">
                                                    <div className="flex items-center gap-1.5 min-w-0">
                                                    <Workflow className="h-4 w-4 shrink-0 text-primary/80" />
                                                    <span className="line-clamp-1">{board.name}</span>
                                                </div>
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="h-7 w-7 p-0 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                                        >
                                                            <MoreVertical className="h-3.5 w-3.5" />
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
                                                <CardDescription className="line-clamp-1 mt-0.5 text-xs">
                                                    {board.description}
                                                </CardDescription>
                                            )}
                                        </CardHeader>
                                        <CardContent className="px-3 py-2">
                                            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground mb-2">
                                                <div className="flex items-center gap-1.5">
                                                    <Calendar className="h-3.5 w-3.5 shrink-0" />
                                                    <span>{new Date(board.created_at).toLocaleDateString('ru-RU')}</span>
                                                </div>
                                                <div className="flex items-center gap-1.5">
                                                    <Clock className="h-3.5 w-3.5 shrink-0" />
                                                    <span>{formatDistance(new Date(board.updated_at), new Date(), { addSuffix: true, locale: ru })}</span>
                                                </div>
                                            </div>
                                            <div className="flex flex-wrap gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
                                                <span className="inline-flex items-center gap-1" title="Источники">
                                                    <Database className="h-3 w-3 text-primary/70" />
                                                    {board.source_nodes_count ?? 0} ист.
                                                </span>
                                                <span className="inline-flex items-center gap-1" title="Блоки данных">
                                                    <Boxes className="h-3 w-3 text-primary/70" />
                                                    {board.content_nodes_count ?? 0} блок.
                                                </span>
                                                <span className="inline-flex items-center gap-1" title="Виджеты">
                                                    <BarChart3 className="h-3 w-3 text-primary/70" />
                                                    {board.widget_nodes_count ?? 0} видж.
                                                </span>
                                                <span className="inline-flex items-center gap-1" title="Таблицы данных">
                                                    <Table2 className="h-3 w-3 text-primary/70" />
                                                    {board.tables_count ?? 0} табл.
                                                </span>
                                                <span className="inline-flex items-center gap-1" title="Поля (столбцы)">
                                                    <Columns3 className="h-3 w-3 text-primary/70" />
                                                    {board.columns_count ?? 0} пол.
                                                </span>
                                            </div>
                                        </CardContent>
                                        <CardFooter className="flex items-center justify-end border-t px-3 py-2 text-xs">
                                            <span className="flex items-center gap-1 text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                                                <ArrowRight className="h-3 w-3" />
                                            </span>
                                        </CardFooter>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </section>

                    {/* Vertical divider (visible on lg+) */}
                    <div className="hidden lg:block w-px min-h-[200px] self-stretch bg-border mx-2" aria-hidden />

                    {/* Dashboards section */}
                    <section className="min-w-0 lg:pl-8">
                        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2 mb-2 sm:text-xl">
                            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                <LayoutDashboard className="h-4 w-4" />
                            </span>
                            Дашборды проекта
                        </h2>

                        {dashboardsLoading ? (
                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                {[1, 2, 3].map((i) => (
                                    <Card key={i} className="animate-pulse overflow-hidden border-0 bg-card/50 shadow-sm">
                                        <CardHeader className="p-3">
                                            <div className="h-4 bg-muted rounded-md w-3/4" />
                                            <div className="h-3 bg-muted rounded-md w-1/2 mt-2" />
                                        </CardHeader>
                                    </Card>
                                ))}
                            </div>
                        ) : dashboards.length === 0 ? (
                            <Card className="overflow-hidden border-dashed border-2 bg-card/30">
                                <CardContent className="flex flex-col items-center justify-center py-6">
                                    <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                        <LayoutDashboard className="h-5 w-5" />
                                    </div>
                                    <p className="text-sm font-medium text-foreground mb-1">Нет дашбордов</p>
                                    <Button size="sm" onClick={() => openCreateDashboardDialog(projectId)} className="gap-1.5 rounded-full mt-2">
                                        <Plus className="h-3.5 w-3.5" />
                                        Создать дашборд
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                {dashboards.map((dashboard) => (
                                    <Card
                                        key={dashboard.id}
                                        className="group relative overflow-hidden border bg-card/80 shadow-sm transition-all duration-300 hover:shadow-md hover:border-primary/20 cursor-pointer"
                                        onClick={() => handleDashboardClick(dashboard.id)}
                                    >
                                        {/* Splash/thumbnail — создаётся при сохранении дашборда */}
                                        <div className="relative w-full aspect-video shrink-0 overflow-hidden bg-muted/50">
                                            {dashboard.thumbnail_url ? (
                                                <img
                                                    src={dashboard.thumbnail_url}
                                                    alt=""
                                                    className="h-full w-full object-cover object-top transition-transform duration-300 group-hover:scale-[1.02]"
                                                />
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-primary/5 to-primary/10">
                                                    <LayoutDashboard className="h-10 w-10 text-primary/30" aria-hidden />
                                                </div>
                                            )}
                                        </div>
                                        <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-primary/0 via-primary/30 to-primary/0 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                                        <CardHeader className="p-3 pb-1">
                                            <CardTitle className="flex items-center justify-between gap-2 text-sm font-semibold group-hover:text-primary transition-colors">
                                                <div className="flex items-center gap-1.5 min-w-0">
                                                    <LayoutDashboard className="h-4 w-4 shrink-0 text-primary/80" />
                                                    <span className="line-clamp-1">{dashboard.name}</span>
                                                </div>
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="h-7 w-7 p-0 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                                        >
                                                            <MoreVertical className="h-3.5 w-3.5" />
                                                        </Button>
                                                    </DropdownMenuTrigger>
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem
                                                            onClick={(e) => {
                                                                e.stopPropagation()
                                                                setDashboardToDelete(dashboard)
                                                            }}
                                                            className="text-destructive focus:text-destructive"
                                                        >
                                                            <Trash2 className="h-4 w-4 mr-2" />
                                                            Удалить дашборд
                                                        </DropdownMenuItem>
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
                                            </CardTitle>
                                            {dashboard.description && (
                                                <CardDescription className="line-clamp-1 mt-0.5 text-xs">
                                                    {dashboard.description}
                                                </CardDescription>
                                            )}
                                        </CardHeader>
                                        <CardContent className="px-3 py-1">
                                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground flex-wrap">
                                                <Calendar className="h-3.5 w-3.5 shrink-0" />
                                                <span>{new Date(dashboard.created_at).toLocaleDateString('ru-RU')}</span>
                                                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                                                    {DASHBOARD_STATUS_LABELS[dashboard.status] ?? dashboard.status}
                                                </span>
                                            </div>
                                        </CardContent>
                                        <CardFooter className="flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground">
                                            <span>Дашборд</span>
                                            <span className="flex items-center gap-1 text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                                                <ArrowRight className="h-3 w-3" />
                                            </span>
                                        </CardFooter>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </section>
                    </div>
                </div>
            </div>

            <ConfirmDialog
                open={!!boardToDelete}
                onOpenChange={(open) => !open && setBoardToDelete(null)}
                title="Удалить доску?"
                description={`Вы уверены, что хотите удалить доску "${boardToDelete?.name}"? Все данные, виджеты и комментарии будут безвозвратно удалены.`}
                confirmText="Удалить"
                cancelText="Отмена"
                variant="danger"
                onConfirm={handleDeleteBoard}
                loading={isDeleting}
            />

            <ConfirmDialog
                open={!!dashboardToDelete}
                onOpenChange={(open) => !open && setDashboardToDelete(null)}
                title="Удалить дашборд?"
                description={`Вы уверены, что хотите удалить дашборд "${dashboardToDelete?.name}"? Все элементы дашборда будут удалены.`}
                confirmText="Удалить"
                cancelText="Отмена"
                variant="danger"
                onConfirm={handleDeleteDashboard}
                loading={isDeleting}
            />
        </AppLayout>
    )
}
