import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { FolderKanban, Plus, ChevronRight, ChevronDown, Workflow, LayoutDashboard, Database, MoreHorizontal, Trash2, Sparkles, BarChart3, Table2, Gauge, Type, Component, ArrowLeft, Filter, Star, Ruler, Link2, X, Loader2, Merge } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useProjectStore } from '@/store/projectStore'
import { useBoardStore } from '@/store/boardStore'
import { useDashboardStore } from '@/store/dashboardStore'
import { useLibraryStore, type NodeTableRef } from '@/store/libraryStore'
import { useUIStore } from '@/store/uiStore'
import { useFilterStore } from '@/store/filterStore'
import { cn } from '@/lib/utils'
import { SourceVitrina } from './SourceVitrina'
import type { BoardWithNodes } from '@/types'
import type { Dashboard, ProjectWidget, ProjectTable } from '@/types/dashboard'

/** Icon + color per widget_type stored in config */
const WIDGET_TYPE_ICONS: Record<string, { icon: React.ElementType; color: string }> = {
    chart: { icon: BarChart3, color: 'text-blue-500' },
    table: { icon: Table2, color: 'text-green-500' },
    metric: { icon: Gauge, color: 'text-amber-500' },
    text: { icon: Type, color: 'text-purple-500' },
    custom: { icon: Component, color: 'text-cyan-500' },
}

function getWidgetIcon(widget: ProjectWidget) {
    const wtype = (widget.config as Record<string, any>)?.widget_type || 'custom'
    return WIDGET_TYPE_ICONS[wtype] || WIDGET_TYPE_ICONS.custom
}

function CountBadge({ count }: { count: number }) {
    if (count === 0) return null
    return (
        <span className="inline-flex items-center justify-center text-[10px] font-semibold bg-primary/10 text-primary rounded-full min-w-[18px] h-[18px] px-1.5 tabular-nums leading-none">
            {count}
        </span>
    )
}

interface ProjectExplorerProps {
    /** Context hint to auto-expand relevant sections */
    context?: 'board' | 'dashboard' | 'overview'
}

export function ProjectExplorer({ context = 'overview' }: ProjectExplorerProps) {
    const navigate = useNavigate()
    const { projectId } = useParams()
    const { currentProject } = useProjectStore()
    const { boards, fetchBoards, deleteBoard, deleteWidgetNode } = useBoardStore()
    const { dashboards, fetchDashboards, deleteDashboard } = useDashboardStore()
    const { widgets, tables, nodeTables, fetchWidgets, fetchTables, fetchNodeTables, deleteWidget, deleteTable } = useLibraryStore()
    const { openCreateBoardDialog, openCreateDashboardDialog } = useUIStore()
    const {
        presets, loadPresets, applyPreset, activePresetId,
        dimensions, loadDimensions,
        dimMappings, isLoadingDimMappings,
        loadMappingsForDimension, deleteDimensionMapping, createDimensionMapping,
        deleteDimension, createDimension, mergeDimensions,
    } = useFilterStore()

    // Expanded state for individual dimension items
    const [expandedDims, setExpandedDims] = useState<Record<string, boolean>>({})
    // Add-mapping popover state: dimId → { open, selectedTableId, selectedColumn }
    const [addMappingState, setAddMappingState] = useState<Record<string, {
        open: boolean; tableId: string; column: string
    }>>({})

    // Dimension management state
    const [selectedDimIds, setSelectedDimIds] = useState<Set<string>>(new Set())
    const [createDimOpen, setCreateDimOpen] = useState(false)
    const [createDimForm, setCreateDimForm] = useState({ name: '', display_name: '', dim_type: 'categorical' })
    const [mergeDialogOpen, setMergeDialogOpen] = useState(false)
    const [mergeTargetId, setMergeTargetId] = useState<string>('')
    const [deleteDimId, setDeleteDimId] = useState<string | null>(null)

    const toggleDim = (dimId: string) => {
        const willExpand = !expandedDims[dimId]
        setExpandedDims((prev) => ({ ...prev, [dimId]: !prev[dimId] }))
        // Load mappings lazily on first expand — outside setState to avoid render side-effects
        if (willExpand && !dimMappings[dimId] && !isLoadingDimMappings[dimId] && projectId) {
            loadMappingsForDimension(projectId, dimId)
        }
    }

    const getAddState = (dimId: string) =>
        addMappingState[dimId] ?? { open: false, tableId: '', column: '' }

    const setAddState = (dimId: string, patch: Partial<{ open: boolean; tableId: string; column: string }>) =>
        setAddMappingState((prev) => ({
            ...prev,
            [dimId]: { ...getAddState(dimId), ...patch },
        }))

    const toggleDimSelect = (e: React.MouseEvent | React.ChangeEvent, dimId: string) => {
        if ('stopPropagation' in e) e.stopPropagation()
        setSelectedDimIds((prev) => {
            const next = new Set(prev)
            if (next.has(dimId)) next.delete(dimId)
            else next.add(dimId)
            return next
        })
    }

    const handleCreateDim = async () => {
        if (!projectId || !createDimForm.name.trim()) return
        await createDimension(projectId, {
            name: createDimForm.name.trim(),
            display_name: createDimForm.display_name.trim() || createDimForm.name.trim(),
            dim_type: createDimForm.dim_type,
        })
        setCreateDimOpen(false)
        setCreateDimForm({ name: '', display_name: '', dim_type: 'categorical' })
    }

    const handleMergeDims = async () => {
        if (!projectId || !mergeTargetId || selectedDimIds.size < 2) return
        const sources = [...selectedDimIds].filter((id) => id !== mergeTargetId)
        await mergeDimensions(projectId, sources, mergeTargetId)
        setMergeDialogOpen(false)
        setSelectedDimIds(new Set())
        setMergeTargetId('')
    }

    const handleAddMapping = async (dimId: string) => {
        if (!projectId) return
        const state = getAddState(dimId)
        const tableRef = nodeTables.find((t) => t.id === state.tableId)
        if (!tableRef || !state.column) return
        await createDimensionMapping(projectId, dimId, {
            node_id: tableRef.nodeId,
            table_name: tableRef.tableName,
            column_name: state.column,
        })
        setAddState(dimId, { open: false, tableId: '', column: '' })
    }

    const [boardToDelete, setBoardToDelete] = useState<BoardWithNodes | null>(null)
    const [dashboardToDelete, setDashboardToDelete] = useState<Dashboard | null>(null)
    const [widgetToDelete, setWidgetToDelete] = useState<ProjectWidget | null>(null)
    const [tableToDelete, setTableToDelete] = useState<ProjectTable | null>(null)
    const [isDeleting, setIsDeleting] = useState(false)

    const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>(() => {
        if (context === 'dashboard') {
            return {
                boards: true,
                dashboards: true,
                library: true,
                tables: false,
                dataSources: false,
                dimensions: true,
            }
        }
        if (context === 'board') {
            return {
                boards: true,
                dashboards: true,
                library: false,
                tables: false,
                dataSources: true,
                dimensions: true,
            }
        }
        return {
            boards: true,
            dashboards: true,
            library: false,
            tables: true,
            dataSources: true,
            dimensions: true,
        }
    })

    useEffect(() => {
        if (projectId) {
            fetchBoards(projectId)
            fetchDashboards(projectId)
            fetchWidgets(projectId)
            fetchTables(projectId)
            loadPresets(projectId)
            loadDimensions(projectId)
        }
    }, [projectId, fetchBoards, fetchDashboards, fetchWidgets, fetchTables, loadPresets, loadDimensions])

    // Fetch node tables when boards change (scoped to current project)
    useEffect(() => {
        if (boards.length > 0 && projectId) {
            // Only fetch for boards belonging to current project
            const projectBoards = boards.filter(b => b.project_id === projectId)
            if (projectBoards.length > 0) {
                fetchNodeTables(projectBoards)
            } else {
                // No boards for this project — clear stale data
                useLibraryStore.setState({ nodeTables: [] })
            }
        } else {
            // No boards at all — clear
            useLibraryStore.setState({ nodeTables: [] })
        }
    }, [boards, projectId, fetchNodeTables])

    const toggleSection = (section: string) => {
        setExpandedSections((prev) => ({
            ...prev,
            [section]: !prev[section],
        }))
    }

    // Раздел открыт только если пользователь его развернул И в нём есть элементы
    const sectionItemCounts: Record<string, number> = {
        dataSources: Infinity,  // каталог — всегда раскрываем
        boards: boards.length,
        dashboards: dashboards.length,
        library: widgets.length + tables.length,
        tables: nodeTables.length,
        dimensions: dimensions.length,
        filters: presets.length,
    }
    const isOpen = (section: string) =>
        !!expandedSections[section] && (sectionItemCounts[section] ?? Infinity) > 0

    const handleBoardClick = (boardId: string) => {
        if (projectId) {
            navigate(`/project/${projectId}/board/${boardId}`)
        }
    }

    const handleDashboardClick = (dashboardId: string) => {
        if (projectId) {
            navigate(`/project/${projectId}/dashboard/${dashboardId}`)
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

    const handleDeleteDashboard = async () => {
        if (!dashboardToDelete) return

        setIsDeleting(true)
        try {
            await deleteDashboard(dashboardToDelete.id)
        } catch (error) {
            console.error('Failed to delete dashboard:', error)
        } finally {
            setIsDeleting(false)
            setDashboardToDelete(null)
        }
    }

    const handleDeleteWidget = async () => {
        if (!widgetToDelete || !projectId) return
        setIsDeleting(true)
        try {
            // Delete from board first if source references exist
            if (widgetToDelete.source_widget_node_id && widgetToDelete.source_board_id) {
                await deleteWidgetNode(widgetToDelete.source_board_id, widgetToDelete.source_widget_node_id, projectId)
            } else {
                // No board source — just delete from library
                await deleteWidget(projectId, widgetToDelete.id)
            }
        } catch (error) {
            console.error('Failed to delete widget:', error)
        } finally {
            setIsDeleting(false)
            setWidgetToDelete(null)
        }
    }

    const handleDeleteTable = async () => {
        if (!tableToDelete || !projectId) return
        setIsDeleting(true)
        try {
            await deleteTable(projectId, tableToDelete.id)
        } catch (error) {
            console.error('Failed to delete table:', error)
        } finally {
            setIsDeleting(false)
            setTableToDelete(null)
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
                <button
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors mb-2"
                    onClick={() => navigate('/welcome')}
                >
                    <ArrowLeft className="h-3 w-3" />
                    <span>Все проекты</span>
                </button>
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
                {/* Data Sources Section - Витрина */}
                <div className="border-b border-border">
                    <button
                        className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                        onClick={() => toggleSection('dataSources')}
                    >
                        {isOpen('dataSources') ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                        <Database className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Источники данных</span>
                    </button>

                    {isOpen('dataSources') && (
                        <div className="pb-2">
                            <p className="px-4 py-1 text-xs text-muted-foreground">
                                Перетащите на доску:
                            </p>
                            <SourceVitrina />
                        </div>
                    )}
                </div>

                {/* Boards Section */}
                <div className="border-b border-border">
                    <div
                        className="w-full px-4 py-2 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer"
                        onClick={() => toggleSection('boards')}
                    >
                        <div className="flex items-center gap-2">
                            {isOpen('boards') ? (
                                <ChevronDown className="h-4 w-4" />
                            ) : (
                                <ChevronRight className="h-4 w-4" />
                            )}
                            <Workflow className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm font-medium">Доски</span>
                            <CountBadge count={boards.length} />
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

                    {isOpen('boards') && (
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
                                            <Workflow className="h-3 w-3 flex-shrink-0" />
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

                {/* Dashboards Section */}
                <div className="border-b border-border">
                    <div
                        className="w-full px-4 py-2 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer"
                        onClick={() => toggleSection('dashboards')}
                    >
                        <div className="flex items-center gap-2">
                            {isOpen('dashboards') ? (
                                <ChevronDown className="h-4 w-4" />
                            ) : (
                                <ChevronRight className="h-4 w-4" />
                            )}
                            <LayoutDashboard className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm font-medium">Дашборды</span>
                            <CountBadge count={dashboards.length} />
                        </div>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={(e) => {
                                e.stopPropagation()
                                openCreateDashboardDialog(projectId)
                            }}
                        >
                            <Plus className="h-4 w-4" />
                        </Button>
                    </div>

                    {isOpen('dashboards') && (
                        <div className="py-1">
                            {dashboards.length === 0 ? (
                                <div className="px-8 py-2 text-xs text-muted-foreground">
                                    Нет дашбордов
                                </div>
                            ) : (
                                dashboards.map((dashboard) => (
                                    <div
                                        key={dashboard.id}
                                        className="group px-8 py-1.5 hover:bg-muted/50 transition-colors flex items-center gap-2"
                                    >
                                        <button
                                            className="flex-1 flex items-center gap-2 text-left text-sm truncate"
                                            onClick={() => handleDashboardClick(dashboard.id)}
                                        >
                                            <LayoutDashboard className="h-3 w-3 flex-shrink-0" />
                                            <span className="truncate">{dashboard.name}</span>
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
                                                        setDashboardToDelete(dashboard)
                                                    }}
                                                    className="text-destructive focus:text-destructive"
                                                >
                                                    <Trash2 className="h-4 w-4 mr-2" />
                                                    Удалить дашборд
                                                </DropdownMenuItem>
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </div>

                {/* Library Section */}
                <div className="border-b border-border">
                    <button
                        className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                        onClick={() => toggleSection('library')}
                    >
                        {isOpen('library') ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                        <Sparkles className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Виджеты</span>
                        <CountBadge count={widgets.length + tables.length} />
                    </button>

                    {isOpen('library') && (
                        <div className="py-1">
                            {widgets.length === 0 && tables.length === 0 ? (
                                <div className="px-8 py-2 text-xs text-muted-foreground">
                                    Виджеты появятся автоматически
                                </div>
                            ) : (
                                <>
                                    {widgets.map((widget) => {
                                        const { icon: WidgetIcon, color } = getWidgetIcon(widget)
                                        return (
                                            <div
                                                key={widget.id}
                                                className="group px-8 py-1.5 hover:bg-muted/50 transition-colors flex items-center gap-2 cursor-grab active:cursor-grabbing"
                                                draggable
                                                onDragStart={(e) => {
                                                    e.dataTransfer.setData('application/gigaboard-widget', JSON.stringify({ id: widget.id, type: 'widget', name: widget.name }))
                                                    e.dataTransfer.effectAllowed = 'copy'
                                                }}
                                            >
                                                <div className="flex-1 flex items-center gap-2 text-left text-sm truncate">
                                                    <WidgetIcon className={`h-3 w-3 flex-shrink-0 ${color}`} />
                                                    <span className="truncate">{widget.name}</span>
                                                </div>
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
                                                                setWidgetToDelete(widget)
                                                            }}
                                                            className="text-destructive focus:text-destructive"
                                                        >
                                                            <Trash2 className="h-4 w-4 mr-2" />
                                                            Удалить виджет
                                                        </DropdownMenuItem>
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
                                            </div>
                                        )
                                    })}
                                    {tables.map((table) => (
                                        <div
                                            key={table.id}
                                            className="group px-8 py-1.5 hover:bg-muted/50 transition-colors flex items-center gap-2 cursor-grab active:cursor-grabbing"
                                            draggable
                                            onDragStart={(e) => {
                                                e.dataTransfer.setData('application/gigaboard-widget', JSON.stringify({ id: table.id, type: 'table', name: table.name }))
                                                e.dataTransfer.effectAllowed = 'copy'
                                            }}
                                        >
                                            <div className="flex-1 flex items-center gap-2 text-left text-sm truncate">
                                                <Table2 className="h-3 w-3 flex-shrink-0 text-green-500" />
                                                <span className="truncate">{table.name}</span>
                                            </div>
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
                                                            setTableToDelete(table)
                                                        }}
                                                        className="text-destructive focus:text-destructive"
                                                    >
                                                        <Trash2 className="h-4 w-4 mr-2" />
                                                        Удалить таблицу
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </div>
                                    ))}
                                </>
                            )}
                        </div>
                    )}
                </div>

                {/* Tables Section */}
                <div className="border-b border-border">
                    <button
                        className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                        onClick={() => toggleSection('tables')}
                    >
                        {isOpen('tables') ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                        <Table2 className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Таблицы</span>
                        <CountBadge count={nodeTables.length} />
                    </button>

                    {isOpen('tables') && (
                        <div className="py-1">
                            {nodeTables.length === 0 ? (
                                <div className="px-8 py-2 text-xs text-muted-foreground">
                                    Таблицы появятся после загрузки данных
                                </div>
                            ) : (
                                nodeTables.map((nt) => (
                                    <div
                                        key={nt.id}
                                        className="group px-8 py-1.5 hover:bg-muted/50 transition-colors flex items-center gap-2 cursor-pointer"
                                        onClick={() => navigate(`/project/${projectId}/board/${nt.boardId}`)}
                                    >
                                        <div className="flex-1 flex items-center gap-2 text-left text-sm truncate min-w-0">
                                            <Table2 className="h-3 w-3 flex-shrink-0 text-emerald-500" />
                                            <span className="truncate">{nt.tableName}</span>
                                            <span className="flex-shrink-0 text-[10px] text-muted-foreground tabular-nums">
                                                {nt.rowCount}×{nt.columnCount}
                                            </span>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </div>

                {/* Dimensions Section */}
                <div className="border-b border-border">
                    {/* Section header row */}
                    <div className="flex items-center">
                        <button
                            className="flex-1 px-4 py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                            onClick={() => toggleSection('dimensions')}
                        >
                            {isOpen('dimensions') ? (
                                <ChevronDown className="h-4 w-4" />
                            ) : (
                                <ChevronRight className="h-4 w-4" />
                            )}
                            <Ruler className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm font-medium">Измерения</span>
                            <CountBadge count={dimensions.length} />
                        </button>
                        {/* Create new dimension */}
                        {isOpen('dimensions') && (
                            <Popover open={createDimOpen} onOpenChange={setCreateDimOpen}>
                                <PopoverTrigger asChild>
                                    <button
                                        className="flex-shrink-0 px-2 py-2 hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground"
                                        title="Добавить измерение"
                                    >
                                        <Plus className="h-4 w-4" />
                                    </button>
                                </PopoverTrigger>
                                <PopoverContent side="right" align="start" className="w-64 p-3">
                                    <p className="text-xs font-medium mb-3">Новое измерение</p>
                                    <div className="space-y-2">
                                        <div>
                                            <p className="text-[11px] text-muted-foreground mb-1">Системное имя *</p>
                                            <Input
                                                className="h-7 text-xs"
                                                placeholder="brand, region, date…"
                                                value={createDimForm.name}
                                                onChange={(e) => setCreateDimForm((f) => ({ ...f, name: e.target.value }))}
                                            />
                                        </div>
                                        <div>
                                            <p className="text-[11px] text-muted-foreground mb-1">Отображаемое имя</p>
                                            <Input
                                                className="h-7 text-xs"
                                                placeholder="Бренд, Регион… (необязательно)"
                                                value={createDimForm.display_name}
                                                onChange={(e) => setCreateDimForm((f) => ({ ...f, display_name: e.target.value }))}
                                            />
                                        </div>
                                        <div>
                                            <p className="text-[11px] text-muted-foreground mb-1">Тип</p>
                                            <Select
                                                value={createDimForm.dim_type}
                                                onValueChange={(v) => setCreateDimForm((f) => ({ ...f, dim_type: v }))}
                                            >
                                                <SelectTrigger className="h-7 text-xs">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="categorical">categorical</SelectItem>
                                                    <SelectItem value="temporal">temporal</SelectItem>
                                                    <SelectItem value="numerical">numerical</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <Button
                                            size="sm"
                                            className="w-full h-7 text-xs"
                                            disabled={!createDimForm.name.trim()}
                                            onClick={handleCreateDim}
                                        >
                                            Создать
                                        </Button>
                                    </div>
                                </PopoverContent>
                            </Popover>
                        )}
                    </div>

                    {isOpen('dimensions') && (
                        <div className="py-1">
                            {/* Multi-select action bar */}
                            {selectedDimIds.size >= 1 && (
                                <div className="mx-3 mb-2 px-2 py-1 rounded-md bg-primary/5 border border-primary/20 flex items-center gap-2">
                                    <span className="flex-1 text-[11px] text-muted-foreground">
                                        Выбрано: {selectedDimIds.size}
                                    </span>
                                    {selectedDimIds.size >= 2 && (
                                        <button
                                            className="flex items-center gap-1 text-[11px] text-primary hover:underline font-medium"
                                            onClick={() => {
                                                setMergeTargetId([...selectedDimIds][0])
                                                setMergeDialogOpen(true)
                                            }}
                                        >
                                            <Merge className="h-3 w-3" />
                                            Объединить
                                        </button>
                                    )}
                                    <button
                                        className="text-[11px] text-muted-foreground hover:text-foreground"
                                        onClick={() => setSelectedDimIds(new Set())}
                                        title="Снять выделение"
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                </div>
                            )}

                            {dimensions.length === 0 ? (
                                <div className="px-8 py-2 text-xs text-muted-foreground">
                                    Измерения будут обнаружены автоматически при загрузке данных
                                </div>
                            ) : (
                                dimensions.map((dim) => {
                                    const isExpanded = !!expandedDims[dim.id]
                                    const isSelected = selectedDimIds.has(dim.id)
                                    const mappings = dimMappings[dim.id] ?? []
                                    const isLoadingMap = !!isLoadingDimMappings[dim.id]
                                    const addState = getAddState(dim.id)
                                    const selectedTable = nodeTables.find((t) => t.id === addState.tableId)
                                    const availableColumns = selectedTable?.columns ?? []

                                    return (
                                        <div key={dim.id}>
                                            {/* Dimension row */}
                                            <div
                                                className={cn(
                                                    'group px-4 py-1.5 hover:bg-muted/50 transition-colors flex items-center gap-1.5',
                                                    isSelected && 'bg-primary/5',
                                                )}
                                            >
                                                {/* Checkbox — visible on hover or when any dim is selected */}
                                                <input
                                                    type="checkbox"
                                                    checked={isSelected}
                                                    className={cn(
                                                        'h-3 w-3 flex-shrink-0 cursor-pointer accent-primary transition-opacity',
                                                        selectedDimIds.size === 0 && 'opacity-0 group-hover:opacity-100',
                                                    )}
                                                    onChange={(e) => toggleDimSelect(e, dim.id)}
                                                    onClick={(e) => e.stopPropagation()}
                                                />

                                                {/* Expand / name area */}
                                                <div
                                                    className="flex-1 flex items-center gap-1.5 min-w-0 cursor-pointer"
                                                    onClick={() => toggleDim(dim.id)}
                                                >
                                                    {isExpanded ? (
                                                        <ChevronDown className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                                                    ) : (
                                                        <ChevronRight className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                                                    )}
                                                    <Ruler className="h-3 w-3 flex-shrink-0 text-indigo-500" />
                                                    <span className="flex-1 text-sm truncate min-w-0">{dim.display_name}</span>
                                                    <span className="flex-shrink-0 text-[10px] text-muted-foreground px-1 py-0.5 rounded bg-muted">
                                                        {dim.dim_type}
                                                    </span>
                                                    {isLoadingMap && (
                                                        <Loader2 className="h-3 w-3 flex-shrink-0 animate-spin text-muted-foreground" />
                                                    )}
                                                    {!isLoadingMap && isExpanded && (
                                                        <CountBadge count={mappings.length} />
                                                    )}
                                                </div>

                                                {/* Actions dropdown */}
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger asChild>
                                                        <button
                                                            className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                                                            onClick={(e) => e.stopPropagation()}
                                                            title="Действия"
                                                        >
                                                            <MoreHorizontal className="h-3.5 w-3.5" />
                                                        </button>
                                                    </DropdownMenuTrigger>
                                                    <DropdownMenuContent align="end" className="w-44">
                                                        <DropdownMenuItem
                                                            onClick={(e) => {
                                                                e.stopPropagation()
                                                                toggleDimSelect(e, dim.id)
                                                            }}
                                                        >
                                                            <Merge className="h-3.5 w-3.5 mr-2" />
                                                            {isSelected ? 'Снять выбор' : 'Выбрать для объединения'}
                                                        </DropdownMenuItem>
                                                        <DropdownMenuSeparator />
                                                        <DropdownMenuItem
                                                            className="text-destructive focus:text-destructive"
                                                            onClick={(e) => {
                                                                e.stopPropagation()
                                                                setDeleteDimId(dim.id)
                                                            }}
                                                        >
                                                            <Trash2 className="h-3.5 w-3.5 mr-2" />
                                                            Удалить измерение
                                                        </DropdownMenuItem>
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
                                            </div>

                                            {/* Expanded: mappings list */}
                                            {isExpanded && (
                                                <div className="pl-8 pb-1">
                                                    {mappings.length === 0 && !isLoadingMap ? (
                                                        <div className="py-1 text-[11px] text-muted-foreground italic">
                                                            Нет ассоциаций
                                                        </div>
                                                    ) : (
                                                        mappings.map((m) => (
                                                            <div
                                                                key={m.id}
                                                                className="group/mapping flex items-center gap-1.5 py-0.5"
                                                            >
                                                                <Link2 className="h-3 w-3 flex-shrink-0 text-muted-foreground/60" />
                                                                <span className="flex-1 text-[11px] text-foreground/80 truncate min-w-0">
                                                                    <span className="font-medium">{m.table_name}</span>
                                                                    <span className="text-muted-foreground mx-0.5">·</span>
                                                                    {m.column_name}
                                                                </span>
                                                                {m.mapping_source === 'auto_detected' && (
                                                                    <span className="flex-shrink-0 text-[9px] text-amber-600 font-medium">
                                                                        auto
                                                                    </span>
                                                                )}
                                                                <button
                                                                    className="flex-shrink-0 opacity-0 group-hover/mapping:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                                                                    title="Удалить ассоциацию"
                                                                    onClick={(e) => {
                                                                        e.stopPropagation()
                                                                        if (projectId) deleteDimensionMapping(projectId, m.id, dim.id)
                                                                    }}
                                                                >
                                                                    <X className="h-3 w-3" />
                                                                </button>
                                                            </div>
                                                        ))
                                                    )}

                                                    {/* Add mapping row */}
                                                    <Popover
                                                        open={addState.open}
                                                        onOpenChange={(open) => setAddState(dim.id, { open })}
                                                    >
                                                        <PopoverTrigger asChild>
                                                            <button
                                                                className="flex items-center gap-1 mt-0.5 text-[11px] text-muted-foreground hover:text-primary transition-colors"
                                                                onClick={(e) => e.stopPropagation()}
                                                            >
                                                                <Plus className="h-3 w-3" />
                                                                <span>Добавить поле</span>
                                                            </button>
                                                        </PopoverTrigger>
                                                        <PopoverContent
                                                            side="right"
                                                            align="start"
                                                            className="w-64 p-3"
                                                            onClick={(e) => e.stopPropagation()}
                                                        >
                                                            <p className="text-xs font-medium mb-2">
                                                                Ассоциировать поле с «{dim.display_name}»
                                                            </p>
                                                            <div className="space-y-2">
                                                                <div>
                                                                    <p className="text-[11px] text-muted-foreground mb-1">Таблица</p>
                                                                    <Select
                                                                        value={addState.tableId}
                                                                        onValueChange={(v) => setAddState(dim.id, { tableId: v, column: '' })}
                                                                    >
                                                                        <SelectTrigger className="h-7 text-xs">
                                                                            <SelectValue placeholder="Выбрать таблицу…" />
                                                                        </SelectTrigger>
                                                                        <SelectContent>
                                                                            {nodeTables.length === 0 ? (
                                                                                <SelectItem value="_none" disabled>
                                                                                    Нет таблиц
                                                                                </SelectItem>
                                                                            ) : (
                                                                                nodeTables.map((t) => (
                                                                                    <SelectItem key={t.id} value={t.id}>
                                                                                        <span className="font-medium">{t.tableName}</span>
                                                                                        <span className="text-muted-foreground ml-1 text-[10px]">
                                                                                            ({t.boardName})
                                                                                        </span>
                                                                                    </SelectItem>
                                                                                ))
                                                                            )}
                                                                        </SelectContent>
                                                                    </Select>
                                                                </div>
                                                                <div>
                                                                    <p className="text-[11px] text-muted-foreground mb-1">Столбец</p>
                                                                    <Select
                                                                        value={addState.column}
                                                                        onValueChange={(v) => setAddState(dim.id, { column: v })}
                                                                        disabled={!addState.tableId}
                                                                    >
                                                                        <SelectTrigger className="h-7 text-xs">
                                                                            <SelectValue placeholder={addState.tableId ? 'Выбрать столбец…' : '← сначала таблицу'} />
                                                                        </SelectTrigger>
                                                                        <SelectContent>
                                                                            {availableColumns.length === 0 ? (
                                                                                <SelectItem value="_none" disabled>
                                                                                    Нет столбцов
                                                                                </SelectItem>
                                                                            ) : (
                                                                                availableColumns.map((col) => (
                                                                                    <SelectItem key={col} value={col}>
                                                                                        {col}
                                                                                    </SelectItem>
                                                                                ))
                                                                            )}
                                                                        </SelectContent>
                                                                    </Select>
                                                                </div>
                                                                <Button
                                                                    size="sm"
                                                                    className="w-full h-7 text-xs"
                                                                    disabled={!addState.tableId || !addState.column}
                                                                    onClick={() => handleAddMapping(dim.id)}
                                                                >
                                                                    Добавить
                                                                </Button>
                                                            </div>
                                                        </PopoverContent>
                                                    </Popover>
                                                </div>
                                            )}
                                        </div>
                                    )
                                })
                            )}
                        </div>
                    )}
                </div>

                {/* Filters / Presets Section */}
                <div className="border-b border-border">
                    <button
                        className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                        onClick={() => toggleSection('filters')}
                    >
                        {isOpen('filters') ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                        <Filter className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Фильтры</span>
                        <CountBadge count={presets.length} />
                    </button>

                    {isOpen('filters') && (
                        <div className="py-1">
                            {presets.length === 0 ? (
                                <div className="px-8 py-2 text-xs text-muted-foreground">
                                    Нет сохранённых пресетов фильтров
                                </div>
                            ) : (
                                presets.map((preset) => (
                                    <div
                                        key={preset.id}
                                        className={cn(
                                            'group px-8 py-1.5 hover:bg-muted/50 transition-colors flex items-center gap-2 cursor-pointer',
                                            preset.id === activePresetId && 'bg-primary/5',
                                        )}
                                        onClick={() => applyPreset(preset.id)}
                                    >
                                        <div className="flex-1 flex items-center gap-2 text-left text-sm truncate min-w-0">
                                            {preset.is_default ? (
                                                <Star className="h-3 w-3 flex-shrink-0 text-amber-500" />
                                            ) : (
                                                <Filter className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                                            )}
                                            <span className="truncate">{preset.name}</span>
                                            {preset.id === activePresetId && (
                                                <span className="flex-shrink-0 text-[10px] text-primary font-medium">
                                                    активен
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
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

            <ConfirmDialog
                open={!!dashboardToDelete}
                onOpenChange={(open) => !open && setDashboardToDelete(null)}
                title="Удалить дашборд?"
                description={`Вы уверены, что хотите удалить дашборд "${dashboardToDelete?.name}"? Все элементы и настройки шаринга будут безвозвратно удалены.`}
                confirmText="Удалить"
                cancelText="Отмена"
                variant="danger"
                onConfirm={handleDeleteDashboard}
                loading={isDeleting}
            />

            <ConfirmDialog
                open={!!widgetToDelete}
                onOpenChange={(open) => !open && setWidgetToDelete(null)}
                title="Удалить виджет из библиотеки?"
                description={`Вы уверены, что хотите удалить виджет "${widgetToDelete?.name}" из библиотеки? Виджет на доске останется.`}
                confirmText="Удалить"
                cancelText="Отмена"
                variant="danger"
                onConfirm={handleDeleteWidget}
                loading={isDeleting}
            />

            <ConfirmDialog
                open={!!tableToDelete}
                onOpenChange={(open) => !open && setTableToDelete(null)}
                title="Удалить таблицу из библиотеки?"
                description={`Вы уверены, что хотите удалить таблицу "${tableToDelete?.name}" из библиотеки?`}
                confirmText="Удалить"
                cancelText="Отмена"
                variant="danger"
                onConfirm={handleDeleteTable}
                loading={isDeleting}
            />

            {/* Delete Dimension Confirm */}
            <ConfirmDialog
                open={!!deleteDimId}
                onOpenChange={(open) => !open && setDeleteDimId(null)}
                title="Удалить измерение?"
                description="Измерение и все его ассоциации будут удалены безвозвратно. Активные фильтры по этому измерению перестанут работать."
                confirmText="Удалить"
                cancelText="Отмена"
                variant="danger"
                onConfirm={() => {
                    if (projectId && deleteDimId) {
                        deleteDimension(projectId, deleteDimId)
                        setSelectedDimIds((prev) => {
                            const next = new Set(prev)
                            next.delete(deleteDimId)
                            return next
                        })
                    }
                    setDeleteDimId(null)
                }}
            />

            {/* Merge Dimensions Dialog */}
            <Dialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
                <DialogContent className="max-w-sm">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Merge className="h-4 w-4" />
                            Объединить измерения
                        </DialogTitle>
                    </DialogHeader>
                    <p className="text-sm text-muted-foreground">
                        Выберите <strong>целевое</strong> измерение — оно останется после объединения.
                        Все ассоциации остальных будут перенесены в него.
                    </p>
                    <div className="space-y-2 mt-1">
                        {[...selectedDimIds].map((id) => {
                            const dim = dimensions.find((d) => d.id === id)
                            if (!dim) return null
                            return (
                                <label
                                    key={id}
                                    className={cn(
                                        'flex items-center gap-3 px-3 py-2 rounded-md border cursor-pointer transition-colors',
                                        mergeTargetId === id
                                            ? 'border-primary bg-primary/5'
                                            : 'border-border hover:bg-muted/50',
                                    )}
                                >
                                    <input
                                        type="radio"
                                        name="mergeTarget"
                                        value={id}
                                        checked={mergeTargetId === id}
                                        onChange={() => setMergeTargetId(id)}
                                        className="accent-primary"
                                    />
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm font-medium truncate">{dim.display_name}</div>
                                        <div className="text-[11px] text-muted-foreground truncate">{dim.name}</div>
                                    </div>
                                    <span className="flex-shrink-0 text-[10px] text-muted-foreground px-1 py-0.5 rounded bg-muted">
                                        {dim.dim_type}
                                    </span>
                                </label>
                            )
                        })}
                    </div>
                    <DialogFooter className="mt-2">
                        <Button variant="ghost" size="sm" onClick={() => setMergeDialogOpen(false)}>
                            Отмена
                        </Button>
                        <Button
                            size="sm"
                            disabled={!mergeTargetId || selectedDimIds.size < 2}
                            onClick={handleMergeDims}
                        >
                            <Merge className="h-3.5 w-3.5 mr-1.5" />
                            Объединить
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
