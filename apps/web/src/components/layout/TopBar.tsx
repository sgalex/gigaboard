/**
 * TopBar - main navigation bar.
 * The center area (#topbar-context) serves as a portal target for
 * context-specific toolbars rendered by BoardCanvas / DashboardPage.
 */
import { Menu, User, LogOut, Settings, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Logo } from '@/components/Logo'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export function TopBar() {
    const { user, logout } = useAuthStore()
    const { toggleProjectExplorer, isAIPanelOpen, toggleAIPanel } = useUIStore()

    return (
        <header className="border-b border-border bg-card select-none">
            <div className="flex h-12 items-center gap-3 px-3">
                {/* Left: Menu toggle + Logo */}
                <div className="flex items-center gap-2 shrink-0">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={toggleProjectExplorer}
                        title="Toggle Project Explorer"
                    >
                        <Menu className="h-4 w-4" />
                    </Button>

                    <Logo variant="light" size={28} className="[&_span:last-child]:text-base" />
                </div>

                <div className="w-px h-6 bg-border" />

                {/* Center: portal target for context-specific actions */}
                <div id="topbar-context" className="flex-1 flex items-center gap-2 min-w-0" />

                {/* Right: AI Panel toggle + Theme toggle + User menu */}
                <div className="flex items-center gap-1 shrink-0">
                    {user && (
                        <Button
                            variant={isAIPanelOpen ? "default" : "ghost"}
                            size="icon"
                            className="h-8 w-8 relative"
                            onClick={toggleAIPanel}
                            title={isAIPanelOpen ? 'Скрыть AI помощник' : 'Показать AI помощник'}
                        >
                            <Sparkles className="h-4 w-4" />
                            {isAIPanelOpen && (
                                <span className="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full" />
                            )}
                        </Button>
                    )}

                    <ThemeToggle />

                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                                <User className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-56">
                            <DropdownMenuLabel>
                                <div className="flex flex-col">
                                    <span className="font-medium">{user?.username}</span>
                                    <span className="text-xs text-muted-foreground">{user?.email}</span>
                                </div>
                            </DropdownMenuLabel>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem>
                                <Settings className="mr-2 h-4 w-4" />
                                <span>Настройки</span>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={logout}>
                                <LogOut className="mr-2 h-4 w-4" />
                                <span>Выйти</span>
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>
        </header>
    )
}
