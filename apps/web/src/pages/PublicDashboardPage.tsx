/**
 * PublicDashboardPage — view a shared dashboard without authentication.
 * See docs/DASHBOARD_SYSTEM.md
 */
import { useEffect, useState, useCallback } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { publicAPI } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { PublicDashboard, ItemBreakpointLayout, DashboardItem } from '@/types/dashboard'

function getBreakpoint(width: number): 'desktop' | 'tablet' | 'mobile' {
    if (width < 480) return 'mobile'
    if (width < 900) return 'tablet'
    return 'desktop'
}

function getItemLayout(item: DashboardItem, bp: 'desktop' | 'tablet' | 'mobile'): ItemBreakpointLayout {
    const layout = item.layout
    if (!layout) return { x: 0, y: 0, width: 400, height: 300, visible: true }
    return layout[bp] || layout.desktop || { x: 0, y: 0, width: 400, height: 300, visible: true }
}

export function PublicDashboardPage() {
    const { token } = useParams()
    const [searchParams] = useSearchParams()
    const [dashboard, setDashboard] = useState<PublicDashboard | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [needPassword, setNeedPassword] = useState(false)
    const [password, setPassword] = useState('')
    const [isLoading, setIsLoading] = useState(true)

    const fetchDashboard = useCallback(async (pwd?: string) => {
        if (!token) return

        setIsLoading(true)
        setError(null)
        try {
            const { data } = await publicAPI.getDashboard(token, pwd)
            setDashboard(data)
            setNeedPassword(false)
        } catch (err: any) {
            const status = err.response?.status
            if (status === 401) {
                setNeedPassword(true)
                if (pwd) setError('Неверный пароль')
            } else if (status === 410) {
                setError('Ссылка истекла или достигнут лимит просмотров')
            } else {
                setError('Дашборд не найден')
            }
        } finally {
            setIsLoading(false)
        }
    }, [token])

    useEffect(() => {
        fetchDashboard()
    }, [fetchDashboard])

    const handlePasswordSubmit = () => {
        fetchDashboard(password)
    }

    if (isLoading) {
        return (
            <div className="h-screen flex items-center justify-center bg-background">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
        )
    }

    if (needPassword) {
        return (
            <div className="h-screen flex items-center justify-center bg-background">
                <div className="max-w-sm w-full p-6 space-y-4">
                    <div className="text-center">
                        <Lock className="h-10 w-10 text-muted-foreground mx-auto" />
                        <h2 className="mt-3 text-lg font-semibold">Защищённый дашборд</h2>
                        <p className="text-sm text-muted-foreground">Для просмотра введите пароль</p>
                    </div>
                    {error && <p className="text-sm text-destructive text-center">{error}</p>}
                    <Input
                        type="password"
                        placeholder="Пароль"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handlePasswordSubmit()}
                    />
                    <Button className="w-full" onClick={handlePasswordSubmit}>
                        Открыть
                    </Button>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="h-screen flex items-center justify-center bg-background">
                <p className="text-muted-foreground">{error}</p>
            </div>
        )
    }

    if (!dashboard) return null

    const bp = getBreakpoint(window.innerWidth)
    const canvasWidth = dashboard.settings?.canvas_width ?? 1440

    return (
        <div className="min-h-screen bg-muted/10">
            {/* Header */}
            <div className="border-b border-border bg-background px-4 py-3">
                <h1 className="text-lg font-semibold">{dashboard.name}</h1>
                {dashboard.description && (
                    <p className="text-sm text-muted-foreground">{dashboard.description}</p>
                )}
            </div>

            {/* Canvas */}
            <div className="flex justify-center p-4">
                <div
                    className="relative bg-background border border-border rounded-lg"
                    style={{ width: Math.min(canvasWidth, window.innerWidth - 32), minHeight: 400 }}
                >
                    {dashboard.items
                        .sort((a, b) => a.z_index - b.z_index)
                        .map(item => {
                            const layout = getItemLayout(item, bp)
                            if (!layout.visible) return null

                            // Simple scaling for responsive
                            const scale = Math.min(1, (window.innerWidth - 32) / canvasWidth)

                            return (
                                <div
                                    key={item.id}
                                    className="absolute bg-card border border-border rounded-md overflow-hidden"
                                    style={{
                                        left: layout.x * scale,
                                        top: layout.y * scale,
                                        width: layout.width * scale,
                                        height: layout.height * scale,
                                        zIndex: item.z_index,
                                        transform: layout.rotation ? `rotate(${layout.rotation}deg)` : undefined,
                                        transformOrigin: 'center center',
                                    }}
                                >
                                    {item.item_type === 'text' && (
                                        <div className="w-full h-full p-2" style={{ fontSize: (item.content?.fontSize || 16) * scale }}>
                                            {item.content?.text || ''}
                                        </div>
                                    )}
                                    {item.item_type === 'widget' && (
                                        <div className="w-full h-full flex items-center justify-center text-xs text-muted-foreground">
                                            Виджет
                                        </div>
                                    )}
                                    {item.item_type === 'table' && (
                                        <div className="w-full h-full flex items-center justify-center text-xs text-muted-foreground">
                                            Таблица
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                </div>
            </div>

            {/* Footer */}
            <div className="text-center py-4 text-xs text-muted-foreground">
                Powered by GigaBoard
            </div>
        </div>
    )
}
