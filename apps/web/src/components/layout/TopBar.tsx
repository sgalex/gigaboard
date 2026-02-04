/**
 * TopBar - main navigation bar
 */
import { Link } from 'react-router-dom'
import { Menu, Search, User, LogOut, Settings, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
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
        <header className="border-b border-border bg-card">
            <div className="flex h-14 items-center gap-4 px-4">
                {/* Left: Menu toggle + Logo */}
                <div className="flex items-center gap-3">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={toggleProjectExplorer}
                        title="Toggle Project Explorer"
                    >
                        <Menu className="h-5 w-5" />
                    </Button>

                    <Link to="/" className="flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold">
                            GB
                        </div>
                        <span className="text-lg font-semibold">GigaBoard</span>
                    </Link>
                </div>

                {/* Center: Global search (placeholder) */}
                <div className="max-w-xl">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <input
                            type="search"
                            placeholder="Поиск проектов, досок..."
                            className="w-full h-9 pl-9 pr-4 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                    </div>
                </div>

                {/* Spacer */}
                <div className="flex-1"></div>

                {/* Right: AI Panel toggle + Theme toggle + User menu */}
                <div className="flex items-center gap-2">
                    {user && (
                        <Button
                            variant={isAIPanelOpen ? "default" : "outline"}
                            size="icon"
                            onClick={toggleAIPanel}
                            title={isAIPanelOpen ? 'Скрыть AI помощник' : 'Показать AI помощник'}
                            className="relative"
                        >
                            <Sparkles className="h-5 w-5" />
                            {isAIPanelOpen && (
                                <span className="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full" />
                            )}
                        </Button>
                    )}

                    <ThemeToggle />

                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                                <User className="h-5 w-5" />
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
