import { useState, useRef, useEffect } from 'react'
import { DataNode } from '@/types'
import {
    Eye,
    BarChart3,
    GitBranch,
    MessageSquare,
    RefreshCw,
    Download,
    Edit3,
    Trash2,
    Link2,
    ChevronRight,
} from 'lucide-react'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuTrigger,
    DropdownMenuLabel,
} from '@/components/ui/dropdown-menu'

type Side = 'top' | 'right' | 'bottom' | 'left'
type Align = 'start' | 'center' | 'end'

interface DataNodeContextMenuProps {
    dataNode: DataNode
    children: React.ReactNode
    onCreateVisualization?: () => void
    onCreateTransformation?: () => void
    onAddComment?: () => void
    onRefresh?: () => void
    onEdit?: () => void
    onDelete?: () => void
    onViewData?: () => void
    onExport?: (format: 'csv' | 'json' | 'xlsx') => void
    onViewConnections?: () => void
}

export function DataNodeContextMenu({
    dataNode,
    children,
    onCreateVisualization,
    onCreateTransformation,
    onAddComment,
    onRefresh,
    onEdit,
    onDelete,
    onViewData,
    onExport,
    onViewConnections,
}: DataNodeContextMenuProps) {
    const [open, setOpen] = useState(false)
    const [position, setPosition] = useState<{ side: Side; align: Align }>({
        side: 'bottom',
        align: 'start',
    })
    const triggerRef = useRef<HTMLDivElement>(null)

    // Calculate optimal menu position when opening
    useEffect(() => {
        if (open && triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect()
            const menuWidth = 256 // w-64 = 16rem = 256px
            const menuHeight = 400 // approximate height
            const padding = 20

            const viewportWidth = window.innerWidth
            const viewportHeight = window.innerHeight

            // Check available space in each direction
            const spaceRight = viewportWidth - rect.right
            const spaceLeft = rect.left
            const spaceBottom = viewportHeight - rect.bottom
            const spaceTop = rect.top

            // Determine best side
            let side: Side = 'bottom'
            let align: Align = 'start'

            // Priority: right, left, bottom, top
            if (spaceRight >= menuWidth + padding) {
                side = 'right'
                align = spaceTop >= menuHeight / 2 ? 'start' : 'end'
            } else if (spaceLeft >= menuWidth + padding) {
                side = 'left'
                align = spaceTop >= menuHeight / 2 ? 'start' : 'end'
            } else if (spaceBottom >= menuHeight + padding) {
                side = 'bottom'
                align = spaceRight >= menuWidth ? 'start' : 'end'
            } else if (spaceTop >= menuHeight + padding) {
                side = 'top'
                align = spaceRight >= menuWidth ? 'start' : 'end'
            } else {
                // Fallback: use side with most space
                const maxSpace = Math.max(spaceRight, spaceLeft, spaceBottom, spaceTop)
                if (maxSpace === spaceRight) side = 'right'
                else if (maxSpace === spaceLeft) side = 'left'
                else if (maxSpace === spaceBottom) side = 'bottom'
                else side = 'top'
            }

            setPosition({ side, align })
        }
    }, [open])

    const handleCreateVisualization = () => {
        setOpen(false)
        onCreateVisualization?.()
    }

    const handleCreateTransformation = () => {
        setOpen(false)
        onCreateTransformation?.()
    }

    const handleAddComment = () => {
        setOpen(false)
        onAddComment?.()
    }

    const handleRefresh = () => {
        setOpen(false)
        onRefresh?.()
    }

    const handleEdit = () => {
        setOpen(false)
        onEdit?.()
    }

    const handleDelete = () => {
        setOpen(false)
        onDelete?.()
    }

    const handleViewData = () => {
        setOpen(false)
        onViewData?.()
    }

    const handleExport = (format: 'csv' | 'json' | 'xlsx') => {
        setOpen(false)
        onExport?.(format)
    }

    const handleViewConnections = () => {
        setOpen(false)
        onViewConnections?.()
    }

    return (
        <DropdownMenu open={open} onOpenChange={setOpen} modal={false}>
            <DropdownMenuTrigger asChild>
                <div ref={triggerRef}>
                    {children}
                </div>
            </DropdownMenuTrigger>
            <DropdownMenuContent
                className="w-64"
                side={position.side}
                align={position.align}
                sideOffset={8}
                alignOffset={0}
                collisionPadding={10}
            >
                {/* Просмотр данных */}
                <DropdownMenuItem onClick={handleViewData}>
                    <Eye className="mr-2 h-4 w-4" />
                    <span>Просмотр данных</span>
                </DropdownMenuItem>

                <DropdownMenuSeparator />

                {/* 🎨 Визуализация */}
                <DropdownMenuItem onClick={handleCreateVisualization}>
                    <BarChart3 className="mr-2 h-4 w-4" />
                    <span>Создать визуализацию</span>
                    <span className="ml-auto text-xs text-muted-foreground">AI</span>
                </DropdownMenuItem>

                {/* ⚙️ Трансформация */}
                <DropdownMenuItem onClick={handleCreateTransformation}>
                    <GitBranch className="mr-2 h-4 w-4" />
                    <span>Создать трансформацию</span>
                    <span className="ml-auto text-xs text-muted-foreground">AI</span>
                </DropdownMenuItem>

                {/* 💬 Комментарий */}
                <DropdownMenuItem onClick={handleAddComment}>
                    <MessageSquare className="mr-2 h-4 w-4" />
                    <span>Добавить комментарий</span>
                </DropdownMenuItem>

                <DropdownMenuSeparator />

                {/* 🔗 Связи */}
                <DropdownMenuItem onClick={handleViewConnections}>
                    <Link2 className="mr-2 h-4 w-4" />
                    <span>Просмотр связей</span>
                </DropdownMenuItem>

                {/* 🔄 Обновить */}
                <DropdownMenuItem onClick={handleRefresh}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    <span>Обновить данные</span>
                </DropdownMenuItem>

                {/* 📤 Экспорт */}
                <DropdownMenuSub>
                    <DropdownMenuSubTrigger>
                        <Download className="mr-2 h-4 w-4" />
                        <span>Экспорт</span>
                    </DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                        <DropdownMenuItem onClick={() => handleExport('csv')}>
                            Экспорт в CSV
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleExport('json')}>
                            Экспорт в JSON
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleExport('xlsx')}>
                            Экспорт в Excel
                        </DropdownMenuItem>
                    </DropdownMenuSubContent>
                </DropdownMenuSub>

                <DropdownMenuSeparator />

                {/* ✏️ Редактировать */}
                <DropdownMenuItem onClick={handleEdit}>
                    <Edit3 className="mr-2 h-4 w-4" />
                    <span>Редактировать</span>
                </DropdownMenuItem>

                {/* Удалить */}
                <DropdownMenuItem
                    onClick={handleDelete}
                    className="text-red-600 dark:text-red-400 focus:bg-red-50 dark:focus:bg-red-950/30 focus:text-red-700 dark:focus:text-red-300"
                >
                    <Trash2 className="mr-2 h-4 w-4" />
                    <span>Удалить узел</span>
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
