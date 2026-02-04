import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, FolderKanban, Calendar, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { useProjectStore } from '@/store/projectStore'
import { useUIStore } from '@/store/uiStore'
import { formatDistance } from 'date-fns'
import { ru } from 'date-fns/locale'

export function WelcomePage() {
    const navigate = useNavigate()
    const { projects, isLoading, fetchProjects } = useProjectStore()
    const { openCreateProjectDialog } = useUIStore()

    useEffect(() => {
        fetchProjects()
    }, [fetchProjects])

    const handleProjectClick = (projectId: string) => {
        navigate(`/project/${projectId}`)
    }

    const formatDate = (dateString: string) => {
        try {
            const date = new Date(dateString)
            return formatDistance(date, new Date(), { addSuffix: true, locale: ru })
        } catch {
            return dateString
        }
    }

    return (
        <div className="h-full overflow-y-auto bg-background">
            <div className="container mx-auto py-8 px-4 max-w-7xl">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-4xl font-bold text-foreground mb-2">Добро пожаловать в GigaBoard</h1>
                    <p className="text-muted-foreground">
                        Интеллектуальная аналитическая доска с AI-ассистентом
                    </p>
                </div>

                {/* Quick Actions */}
                <div className="mb-8 flex gap-4">
                    <Button onClick={openCreateProjectDialog} size="lg" className="gap-2">
                        <Plus className="h-5 w-5" />
                        Создать проект
                    </Button>
                </div>

                {/* Projects Grid */}
                <div>
                    <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
                        <FolderKanban className="h-6 w-6" />
                        Мои проекты
                    </h2>

                    {isLoading ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {[1, 2, 3].map((i) => (
                                <Card key={i} className="animate-pulse">
                                    <CardHeader>
                                        <div className="h-6 bg-muted rounded w-3/4 mb-2"></div>
                                        <div className="h-4 bg-muted rounded w-1/2"></div>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="h-4 bg-muted rounded w-full mb-2"></div>
                                        <div className="h-4 bg-muted rounded w-2/3"></div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : projects.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="flex flex-col items-center justify-center py-12">
                                <FolderKanban className="h-16 w-16 text-muted-foreground mb-4" />
                                <p className="text-lg font-medium text-foreground mb-2">Нет проектов</p>
                                <p className="text-sm text-muted-foreground mb-4">
                                    Создайте первый проект, чтобы начать работу
                                </p>
                                <Button onClick={openCreateProjectDialog} className="gap-2">
                                    <Plus className="h-4 w-4" />
                                    Создать проект
                                </Button>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {projects.map((project) => (
                                <Card
                                    key={project.id}
                                    className="hover:shadow-lg transition-shadow cursor-pointer group"
                                    onClick={() => handleProjectClick(project.id)}
                                >
                                    <CardHeader>
                                        <CardTitle className="flex items-center gap-2 group-hover:text-primary transition-colors">
                                            <FolderKanban className="h-5 w-5" />
                                            {project.name}
                                        </CardTitle>
                                        {project.description && (
                                            <CardDescription className="line-clamp-2">{project.description}</CardDescription>
                                        )}
                                    </CardHeader>
                                    <CardContent>
                                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                            <div className="flex items-center gap-1">
                                                <Calendar className="h-4 w-4" />
                                                <span>{new Date(project.created_at).toLocaleDateString('ru-RU')}</span>
                                            </div>
                                            <div className="flex items-center gap-1">
                                                <Clock className="h-4 w-4" />
                                                <span>{formatDate(project.updated_at)}</span>
                                            </div>
                                        </div>
                                    </CardContent>
                                    <CardFooter className="text-xs text-muted-foreground">
                                        {(project as any).boards_count || 0} {(project as any).boards_count === 1 ? 'доска' : 'досок'}
                                    </CardFooter>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
