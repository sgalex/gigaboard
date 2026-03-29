/**
 * TopBar - main navigation bar.
 * The center area (#topbar-context) serves as a portal target for
 * context-specific toolbars rendered by BoardCanvas / DashboardPage.
 */
import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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

interface TopBarProps {
    /** X-координата левого края колонки `main` в окне (сайдбар + ручка ресайза), px */
    contextMainOffset?: number
}

/** `gap-3` в flex-ряду шапки */
const TOPBAR_GAP_PX = 12

export function TopBar({ contextMainOffset = 0 }: TopBarProps) {
    const navigate = useNavigate()
    const { user, logout } = useAuthStore()
    const { toggleProjectExplorer, isAIPanelOpen, toggleAIPanel } = useUIStore()

    const leftClusterRef = useRef<HTMLDivElement>(null)
    const [spacerWidth, setSpacerWidth] = useState(0)

    const updateSpacerWidth = useCallback(() => {
        const el = leftClusterRef.current
        if (!el) return
        const right = el.getBoundingClientRect().right
        // Левый край #topbar-context = right + gap + spacer + gap = contextMainOffset
        setSpacerWidth(Math.max(0, contextMainOffset - right - 2 * TOPBAR_GAP_PX))
    }, [contextMainOffset])

    useLayoutEffect(() => {
        updateSpacerWidth()
        const el = leftClusterRef.current
        if (!el) return
        const ro = new ResizeObserver(() => updateSpacerWidth())
        ro.observe(el)
        window.addEventListener('resize', updateSpacerWidth)
        return () => {
            ro.disconnect()
            window.removeEventListener('resize', updateSpacerWidth)
        }
    }, [updateSpacerWidth])

    return (
        <header className="border-b border-border bg-card select-none">
            <div className="flex h-12 items-center gap-3 px-3">
                {/* Left: Menu + Logo — ширина учитывается в спейсере */}
                <div ref={leftClusterRef} className="flex items-center gap-2 shrink-0">
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

                {/* Доводит левый край контекстного тулбара до левого края доски под сайдбаром */}
                <div
                    className="shrink-0 transition-[width] duration-300 ease-out"
                    style={{ width: spacerWidth }}
                    aria-hidden
                />

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
                            title={isAIPanelOpen ? 'Скрыть ИИ-ассистента' : 'Показать ИИ-ассистента'}
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
                            <DropdownMenuItem onClick={() => navigate('/profile')}>
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
