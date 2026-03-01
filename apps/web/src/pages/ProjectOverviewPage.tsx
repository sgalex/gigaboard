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
} from 'lucide-react'
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
    const { currentProject, fetchProject } = useProjectStore()
    const { boards, fetchBoards, deleteBoard, isLoading: boardsLoading } = useBoardStore()
    const { dashboards, fetchDashboards, deleteDashboard, isLoading: dashboardsLoading } = useDashboardStore()
    const { openCreateBoardDialog, openCreateDashboardDialog } = useUIStore()
    const [boardToDelete, setBoardToDelete] = useState<BoardWithNodes | null>(null)
    const [dashboardToDelete, setDashboardToDelete] = useState<Dashboard | null>(null)
    const [isDeleting, setIsDeleting] = useState(false)

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
            <div className="min-h-full overflow-y-auto bg-transparent">
                {/* Thematic background */}
                <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
                    <div className="absolute -top-40 -right-40 h-80 w-80 rounded-full bg-primary/8 blur-3xl" />
                    <div className="absolute top-1/2 -left-40 h-96 w-96 rounded-full bg-primary/6 blur-3xl" />
                    <div
                        className="absolute inset-0 opacity-[0.4] dark:opacity-[0.25]"
                        style={{
                            backgroundImage: `
                                linear-gradient(hsl(var(--foreground) / 0.03) 1px, transparent 1px),
                                linear-gradient(90deg, hsl(var(--foreground) / 0.03) 1px, transparent 1px)
                            `,
                            backgroundSize: '24px 24px',
                        }}
                    />
                    <div
                        className="absolute inset-0 opacity-[0.5] dark:opacity-[0.35]"
                        style={{
                            backgroundImage: `
                                linear-gradient(hsl(var(--primary) / 0.06) 1px, transparent 1px),
                                linear-gradient(90deg, hsl(var(--primary) / 0.06) 1px, transparent 1px)
                            `,
                            backgroundSize: '96px 96px',
                        }}
                    />
                </div>

                <div className="relative max-w-6xl mx-auto px-4 py-4 sm:py-5">
                    {/* Project header */}
                    <header className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div className="min-w-0">
                            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                                {currentProject.name}
                            </h1>
                            {currentProject.description && (
                                <p className="text-sm text-muted-foreground mt-0.5 line-clamp-1">
                                    {currentProject.description}
                                </p>
                            )}
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

                    {/* Boards + Dashboards: two columns on lg */}
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-8">
                    {/* Boards section */}
                    <section className="min-w-0">
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

                    {/* Dashboards section */}
                    <section className="min-w-0">
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
