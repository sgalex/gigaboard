import { Menu, Search, User, Settings, LogOut, PanelLeftClose, PanelLeftOpen, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { useNavigate } from 'react-router-dom'

export function TopBar() {
    const { user, logout } = useAuthStore()
    const { isProjectExplorerOpen, isAIPanelOpen, toggleProjectExplorer, toggleAIPanel } = useUIStore()
    const navigate = useNavigate()

    const handleLogout = () => {
        logout()
        navigate('/login')
    }

    return (
        <header className="h-14 border-b border-border bg-card flex items-center justify-between px-4">
            {/* Left section */}
            <div className="flex items-center gap-2">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleProjectExplorer}
                    title={isProjectExplorerOpen ? 'Скрыть панель' : 'Показать панель'}
                >
                    {isProjectExplorerOpen ? <PanelLeftClose className="h-5 w-5" /> : <PanelLeftOpen className="h-5 w-5" />}
                </Button>

                <div className="flex items-center gap-2 ml-2">
                    <Menu className="h-6 w-6 text-primary" />
                    <h1 className="text-xl font-bold text-foreground">GigaBoard</h1>
                </div>
            </div>

            {/* Center section - Search */}
            <div className="max-w-xl ml-4">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                        type="text"
                        placeholder="Поиск по проектам, доскам, виджетам..."
                        className="w-full pl-10 pr-4 py-2 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                </div>
            </div>

            {/* Spacer */}
            <div className="flex-1"></div>

            {/* Right section */}
            <div className="flex items-center gap-3">
                {user && (
                    <Button
                        variant={isAIPanelOpen ? "default" : "outline"}
                        size="icon"
                        onClick={toggleAIPanel}
                        title={isAIPanelOpen ? 'Скрыть ИИ-ассистента' : 'Показать ИИ-ассистента'}
                        className="relative"
                    >
                        <Sparkles className="h-5 w-5" />
                        {isAIPanelOpen && (
                            <span className="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full" />
                        )}
                    </Button>
                )}

                <ThemeToggle />

                {user && (
                    <>
                        {user.role === 'admin' && (
                            <Button
                                variant="outline"
                                size="sm"
                                title="Системные настройки LLM и Playground"
                                onClick={() => navigate('/admin/llm')}
                            >
                                Настройки LLM
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            size="icon"
                            title="Профиль"
                            onClick={() => navigate('/profile')}
                        >
                            <Settings className="h-5 w-5" />
                        </Button>

                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted">
                            <User className="h-4 w-4" />
                            <span className="text-sm font-medium">{user.username}</span>
                            {user.role === 'admin' && (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-primary/20 text-primary font-medium">Админ</span>
                            )}
                        </div>

                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleLogout}
                            title="Выйти"
                        >
                            <LogOut className="h-5 w-5" />
                        </Button>
                    </>
                )}
            </div>
        </header>
    )
}
