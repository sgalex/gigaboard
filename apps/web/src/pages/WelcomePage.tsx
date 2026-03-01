import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, FolderKanban, Calendar, Clock, Sparkles, ArrowRight, LayoutDashboard, Workflow, Database, BarChart3, Table2, Boxes, Ruler, Filter, Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
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
import { useProjectStore } from '@/store/projectStore'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import type { ProjectWithBoards } from '@/types'
import { formatDistance } from 'date-fns'
import { ru } from 'date-fns/locale'

export function WelcomePage() {
    const navigate = useNavigate()
    const { user } = useAuthStore()
    const { projects, isLoading, fetchProjects, updateProject, deleteProject } = useProjectStore()
    const { openCreateProjectDialog } = useUIStore()
    const [projectToDelete, setProjectToDelete] = useState<ProjectWithBoards | null>(null)
    const [projectToEdit, setProjectToEdit] = useState<ProjectWithBoards | null>(null)
    const [editName, setEditName] = useState('')
    const [editDescription, setEditDescription] = useState('')
    const [isDeleting, setIsDeleting] = useState(false)
    const [isSaving, setIsSaving] = useState(false)

    useEffect(() => {
        fetchProjects()
    }, [fetchProjects])

    useEffect(() => {
        if (projectToEdit) {
            setEditName(projectToEdit.name)
            setEditDescription(projectToEdit.description ?? '')
        }
    }, [projectToEdit])

    const handleProjectClick = (projectId: string) => {
        navigate(`/project/${projectId}`)
    }

    const handleDeleteProject = async () => {
        if (!projectToDelete) return
        setIsDeleting(true)
        try {
            await deleteProject(projectToDelete.id)
        } finally {
            setIsDeleting(false)
            setProjectToDelete(null)
        }
    }

    const handleSaveEdit = async () => {
        if (!projectToEdit) return
        const name = editName.trim()
        if (!name) return
        setIsSaving(true)
        try {
            await updateProject(projectToEdit.id, {
                name,
                description: editDescription.trim() || null,
            })
            setProjectToEdit(null)
        } finally {
            setIsSaving(false)
        }
    }

    const formatDate = (dateString: string) => {
        try {
            const date = new Date(dateString)
            return formatDistance(date, new Date(), { addSuffix: true, locale: ru })
        } catch {
            return dateString
        }
    }

    const fullName = user?.username || user?.email?.split('@')[0] || ''
    const displayName = fullName ? fullName.trim().split(/\s+/)[0] : 'друг'

    return (
        <div className="min-h-full overflow-y-auto bg-transparent">
            {/* Thematic background: canvas/board + soft glow */}
            <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
                {/* Soft gradient orbs */}
                <div className="absolute -top-40 -right-40 h-80 w-80 rounded-full bg-primary/8 blur-3xl" />
                <div className="absolute top-1/2 -left-40 h-96 w-96 rounded-full bg-primary/6 blur-3xl" />
                <div className="absolute bottom-0 right-1/4 h-64 w-64 rounded-full bg-primary/4 blur-3xl" />
                {/* Canvas-style grid — like a board/canvas */}
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
                {/* Bolder axis lines — dashboard/chart feel */}
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
                {/* Subtle radial fade at edges */}
                <div
                    className="absolute inset-0"
                    style={{
                        background: 'radial-gradient(ellipse 80% 60% at 50% 0%, hsl(var(--primary) / 0.04), transparent 50%)',
                    }}
                />
            </div>

            <div className="container relative mx-auto py-10 px-4 max-w-6xl sm:py-12">
                {/* Hero */}
                <header className="mb-12 text-center sm:mb-16">
                    <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm font-medium text-primary mb-6">
                        <Sparkles className="h-4 w-4" />
                        AI-аналитика и дашборды
                    </div>
                    <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl mb-3">
                        Привет,{' '}
                        <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
                            {displayName}
                        </span>
                    </h1>
                    <p className="mx-auto max-w-xl text-lg text-muted-foreground sm:text-xl">
                        Добро пожаловать в GigaBoard — создавайте проекты, стройте пайплайны и дашборды с помощью AI.
                    </p>
                    <div className="mt-8 flex flex-wrap justify-center gap-3">
                        <Button
                            onClick={openCreateProjectDialog}
                            size="lg"
                            className="gap-2 rounded-full px-6 shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-shadow"
                        >
                            <Plus className="h-5 w-5" />
                            Создать проект
                        </Button>
                    </div>
                </header>

                {/* Projects Section */}
                <section>
                    <div className="mb-6 flex items-center justify-between">
                        <h2 className="text-xl font-semibold text-foreground flex items-center gap-2 sm:text-2xl">
                            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                <FolderKanban className="h-5 w-5" />
                            </span>
                            Мои проекты
                        </h2>
                    </div>

                    {isLoading ? (
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            {[1, 2, 3].map((i) => (
                                <Card key={i} className="animate-pulse overflow-hidden border-0 bg-card/50 shadow-sm">
                                    <CardHeader>
                                        <div className="h-6 bg-muted rounded-md w-3/4 mb-2" />
                                        <div className="h-4 bg-muted rounded-md w-1/2" />
                                    </CardHeader>
                                    <CardContent>
                                        <div className="h-4 bg-muted rounded-md w-full mb-2" />
                                        <div className="h-4 bg-muted rounded-md w-2/3" />
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : projects.length === 0 ? (
                        <Card className="overflow-hidden border-dashed border-2 bg-card/30 shadow-sm transition-colors hover:border-primary/30 hover:bg-card/50">
                            <CardContent className="flex flex-col items-center justify-center py-16 px-6">
                                <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                    <FolderKanban className="h-10 w-10" />
                                </div>
                                <p className="text-lg font-semibold text-foreground mb-2">Пока нет проектов</p>
                                <p className="text-center text-sm text-muted-foreground mb-6 max-w-sm">
                                    Создайте первый проект — добавьте источники данных, постройте трансформации и дашборды.
                                </p>
                                <Button onClick={openCreateProjectDialog} className="gap-2 rounded-full" size="lg">
                                    <Plus className="h-4 w-4" />
                                    Создать проект
                                </Button>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            {projects.map((project: ProjectWithBoards, index) => (
                                <Card
                                    key={project.id}
                                    className="group relative overflow-hidden border bg-card/80 shadow-sm transition-all duration-300 hover:shadow-md hover:shadow-primary/5 hover:border-primary/20 cursor-pointer animate-scale-in"
                                    style={{ animationDelay: `${index * 50}ms` }}
                                    onClick={() => handleProjectClick(project.id)}
                                >
                                    <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-primary/0 via-primary/30 to-primary/0 opacity-0 transition-opacity group-hover:opacity-100" />
                                    <CardHeader className="pb-2">
                                        <CardTitle className="flex items-center gap-2 text-base font-semibold group-hover:text-primary transition-colors">
                                            <FolderKanban className="h-5 w-5 shrink-0 text-primary/80" />
                                            <span className="line-clamp-1">{project.name}</span>
                                        </CardTitle>
                                        {project.description && (
                                            <CardDescription className="line-clamp-2 mt-1">
                                                {project.description}
                                            </CardDescription>
                                        )}
                                    </CardHeader>
                                    <CardContent className="py-2">
                                        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground mb-3">
                                            <div className="flex items-center gap-1.5">
                                                <Calendar className="h-4 w-4 shrink-0" />
                                                <span>{new Date(project.created_at).toLocaleDateString('ru-RU')}</span>
                                            </div>
                                            <div className="flex items-center gap-1.5">
                                                <Clock className="h-4 w-4 shrink-0" />
                                                <span>{formatDate(project.updated_at)}</span>
                                            </div>
                                        </div>
                                        <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground">
                                            <span className="inline-flex items-center gap-1" title="Доски">
                                                <Workflow className="h-3.5 w-3.5 text-primary/70" />
                                                {project.boards_count ?? 0} досок
                                            </span>
                                            <span className="inline-flex items-center gap-1" title="Дашборды">
                                                <LayoutDashboard className="h-3.5 w-3.5 text-primary/70" />
                                                {project.dashboards_count ?? 0} дашб.
                                            </span>
                                            <span className="inline-flex items-center gap-1" title="Источники">
                                                <Database className="h-3.5 w-3.5 text-primary/70" />
                                                {project.sources_count ?? 0} ист.
                                            </span>
                                            <span className="inline-flex items-center gap-1" title="Блоки данных (узлы контента)">
                                                <Boxes className="h-3.5 w-3.5 text-primary/70" />
                                                {project.content_nodes_count ?? 0} блок.
                                            </span>
                                            <span className="inline-flex items-center gap-1" title="Виджеты">
                                                <BarChart3 className="h-3.5 w-3.5 text-primary/70" />
                                                {project.widgets_count ?? 0} видж.
                                            </span>
                                            <span className="inline-flex items-center gap-1" title="Таблицы данных">
                                                <Table2 className="h-3.5 w-3.5 text-primary/70" />
                                                {project.tables_count ?? 0} табл.
                                            </span>
                                            <span className="inline-flex items-center gap-1" title="Измерения (оси кросс-фильтрации)">
                                                <Ruler className="h-3.5 w-3.5 text-primary/70" />
                                                {project.dimensions_count ?? 0} изм.
                                            </span>
                                            <span className="inline-flex items-center gap-1" title="Пресеты фильтров">
                                                <Filter className="h-3.5 w-3.5 text-primary/70" />
                                                {project.filters_count ?? 0} фильтр.
                                            </span>
                                        </div>
                                    </CardContent>
                                    <CardFooter className="flex items-center justify-between gap-2 border-t pt-3 text-xs opacity-0 transition-opacity group-hover:opacity-100">
                                        <div className="flex items-center gap-2">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-7 px-2 text-muted-foreground hover:text-foreground"
                                                onClick={(e) => {
                                                    e.stopPropagation()
                                                    setProjectToEdit(project)
                                                }}
                                            >
                                                <Pencil className="h-3.5 w-3.5 mr-1" />
                                                Изменить
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-7 px-2 text-muted-foreground hover:text-destructive"
                                                onClick={(e) => {
                                                    e.stopPropagation()
                                                    setProjectToDelete(project)
                                                }}
                                            >
                                                <Trash2 className="h-3.5 w-3.5 mr-1" />
                                                Удалить
                                            </Button>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-7 px-2 text-primary gap-1"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                handleProjectClick(project.id)
                                            }}
                                        >
                                            Открыть
                                            <ArrowRight className="h-3.5 w-3.5" />
                                        </Button>
                                    </CardFooter>
                                </Card>
                            ))}
                        </div>
                    )}
                </section>
            </div>

            <ConfirmDialog
                open={!!projectToDelete}
                onOpenChange={(open) => !open && setProjectToDelete(null)}
                title="Удалить проект?"
                description={
                    projectToDelete
                        ? `Вы уверены, что хотите удалить проект «${projectToDelete.name}»? Все доски, дашборды и данные проекта будут удалены. Это действие нельзя отменить.`
                        : ''
                }
                variant="danger"
                confirmText="Удалить"
                onConfirm={handleDeleteProject}
                loading={isDeleting}
            />

            <Dialog open={!!projectToEdit} onOpenChange={(open) => !open && setProjectToEdit(null)}>
                <DialogContent className="sm:max-w-md" onClick={(e) => e.stopPropagation()}>
                    <DialogHeader>
                        <DialogTitle>Редактировать проект</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                            <Label htmlFor="edit-project-name">Название</Label>
                            <Input
                                id="edit-project-name"
                                value={editName}
                                onChange={(e) => setEditName(e.target.value)}
                                placeholder="Название проекта"
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="edit-project-desc">Описание</Label>
                            <Textarea
                                id="edit-project-desc"
                                value={editDescription}
                                onChange={(e) => setEditDescription(e.target.value)}
                                placeholder="Краткое описание (необязательно)"
                                rows={3}
                                className="resize-none"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setProjectToEdit(null)} disabled={isSaving}>
                            Отмена
                        </Button>
                        <Button onClick={handleSaveEdit} disabled={isSaving || !editName.trim()}>
                            {isSaving ? 'Сохранение...' : 'Сохранить'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
