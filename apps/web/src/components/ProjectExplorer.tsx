import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { FolderKanban, Plus, ChevronRight, ChevronDown, LayoutDashboard, Database, FileText, Wrench, FileBarChart, MoreHorizontal, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useProjectStore } from '@/store/projectStore'
import { useBoardStore } from '@/store/boardStore'
import { useUIStore } from '@/store/uiStore'
import { cn } from '@/lib/utils'
import { SourceVitrina } from './SourceVitrina'
import type { BoardWithNodes } from '@/types'

export function ProjectExplorer() {
    const navigate = useNavigate()
    const { projectId } = useParams()
    const { currentProject } = useProjectStore()
    const { boards, fetchBoards, deleteBoard } = useBoardStore()
    const { openCreateBoardDialog } = useUIStore()
    const [boardToDelete, setBoardToDelete] = useState<BoardWithNodes | null>(null)
    const [isDeleting, setIsDeleting] = useState(false)

    const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
        boards: true,
        dataSources: true,
        artifacts: false,
        workflows: false,
        reports: false,
    })

    useEffect(() => {
        if (projectId) {
            fetchBoards(projectId)
        }
    }, [projectId, fetchBoards])

    const toggleSection = (section: string) => {
        setExpandedSections((prev) => ({
            ...prev,
            [section]: !prev[section],
        }))
    }

    const handleBoardClick = (boardId: string) => {
        if (projectId) {
            navigate(`/project/${projectId}/board/${boardId}`)
        }
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
            <div className="p-4 text-center text-muted-foreground">
                <p className="text-sm">Выберите проект</p>
            </div>
        )
    }

    return (
        <div className="h-full flex flex-col">
            {/* Project Header */}
            <div className="p-4 border-b border-border">
                <div className="flex items-center gap-2">
                    <FolderKanban className="h-5 w-5 text-primary" />
                    <h2 className="font-semibold text-foreground truncate">{currentProject.name}</h2>
                </div>
                {currentProject.description && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{currentProject.description}</p>
                )}
            </div>

            {/* Tree Sections */}
            <div className="flex-1 overflow-y-auto">
                {/* Boards Section */}
                <div className="border-b border-border">
                    <div
                        className="w-full px-4 py-2 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer"
                        onClick={() => toggleSection('boards')}
                    >
                        <div className="flex items-center gap-2">
                            {expandedSections.boards ? (
                                <ChevronDown className="h-4 w-4" />
                            ) : (
                                <ChevronRight className="h-4 w-4" />
                            )}
                            <LayoutDashboard className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm font-medium">Доски</span>
                            <span className="text-xs text-muted-foreground">({boards.length})</span>
                        </div>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={(e) => {
                                e.stopPropagation()
                                openCreateBoardDialog(projectId)
                            }}
                        >
                            <Plus className="h-4 w-4" />
                        </Button>
                    </div>

                    {expandedSections.boards && (
                        <div className="py-1">
                            {boards.length === 0 ? (
                                <div className="px-8 py-2 text-xs text-muted-foreground">
                                    Нет досок
                                </div>
                            ) : (
                                boards.map((board) => (
                                    <div
                                        key={board.id}
                                        className="group px-8 py-1.5 hover:bg-muted/50 transition-colors flex items-center gap-2"
                                    >
                                        <button
                                            className="flex-1 flex items-center gap-2 text-left text-sm truncate"
                                            onClick={() => handleBoardClick(board.id)}
                                        >
                                            <LayoutDashboard className="h-3 w-3 flex-shrink-0" />
                                            <span className="truncate">{board.name}</span>
                                        </button>
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                                                    onClick={(e) => e.stopPropagation()}
                                                >
                                                    <MoreHorizontal className="h-3 w-3" />
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
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </div>

                {/* Data Sources Section - Витрина */}
                <div className="border-b border-border">
                    <button
                        className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                        onClick={() => toggleSection('dataSources')}
                    >
                        {expandedSections.dataSources ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                        <Database className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Источники данных</span>
                    </button>

                    {expandedSections.dataSources && (
                        <div className="pb-2">
                            <p className="px-4 py-1 text-xs text-muted-foreground">
                                Перетащите на доску:
                            </p>
                            <SourceVitrina />
                        </div>
                    )}
                </div>

                {/* Artifacts Section */}
                <div className="border-b border-border">
                    <button
                        className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                        onClick={() => toggleSection('artifacts')}
                    >
                        {expandedSections.artifacts ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Артефакты</span>
                        <span className="text-xs text-muted-foreground">(0)</span>
                    </button>
                </div>

                {/* Workflows Section */}
                <div className="border-b border-border">
                    <button
                        className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                        onClick={() => toggleSection('workflows')}
                    >
                        {expandedSections.workflows ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                        <Wrench className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Инструменты</span>
                        <span className="text-xs text-muted-foreground">(0)</span>
                    </button>
                </div>

                {/* Reports Section */}
                <div>
                    <button
                        className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                        onClick={() => toggleSection('reports')}
                    >
                        {expandedSections.reports ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                        <FileBarChart className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Отчёты</span>
                        <span className="text-xs text-muted-foreground">(0)</span>
                    </button>
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
        </div>
    )
}
