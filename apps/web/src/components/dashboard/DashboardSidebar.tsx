/**
 * DashboardSidebar — list of library widgets & tables for adding to dashboard.
 * See docs/DASHBOARD_SYSTEM.md
 */
import { BarChart3, Table2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ProjectWidget, ProjectTable } from '@/types/dashboard'

interface DashboardSidebarProps {
    widgets: ProjectWidget[]
    tables: ProjectTable[]
    onAddWidget: (widgetId: string) => void
    onAddTable: (tableId: string) => void
    onClose: () => void
}

export function DashboardSidebar({ widgets, tables, onAddWidget, onAddTable, onClose }: DashboardSidebarProps) {
    return (
        <div className="w-56 border-r border-border bg-background flex flex-col shrink-0">
            <div className="p-3 border-b border-border flex items-center justify-between">
                <span className="text-sm font-medium">Библиотека</span>
                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
                    <X className="h-3.5 w-3.5" />
                </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-3">
                {/* Widgets */}
                {widgets.length > 0 && (
                    <div>
                        <p className="text-xs font-medium text-muted-foreground px-1 mb-1">Виджеты</p>
                        <div className="space-y-1">
                            {widgets.map(w => (
                                <button
                                    key={w.id}
                                    className="w-full text-left px-2 py-1.5 rounded-md hover:bg-muted/50 transition-colors flex items-center gap-2 text-sm"
                                    onClick={() => onAddWidget(w.id)}
                                >
                                    <BarChart3 className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                                    <span className="truncate">{w.name}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Tables */}
                {tables.length > 0 && (
                    <div>
                        <p className="text-xs font-medium text-muted-foreground px-1 mb-1">Таблицы</p>
                        <div className="space-y-1">
                            {tables.map(t => (
                                <button
                                    key={t.id}
                                    className="w-full text-left px-2 py-1.5 rounded-md hover:bg-muted/50 transition-colors flex items-center gap-2 text-sm"
                                    onClick={() => onAddTable(t.id)}
                                >
                                    <Table2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                                    <span className="truncate">{t.name}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {widgets.length === 0 && tables.length === 0 && (
                    <div className="text-center py-8 text-xs text-muted-foreground">
                        <p>Библиотека пуста</p>
                        <p className="mt-1">Сохраните виджеты и таблицы с досок</p>
                    </div>
                )}
            </div>
        </div>
    )
}
