import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { useAuthStore } from '@/store/authStore'
import { SystemLLMSettingsPanel } from '@/components/settings/SystemLLMSettingsPanel'

export function AdminLLMPage() {
    const { user } = useAuthStore()
    const navigate = useNavigate()

    useEffect(() => {
        if (user?.role !== 'admin') {
            navigate('/profile', { replace: true })
            return
        }
    }, [user?.role, navigate])

    if (user?.role !== 'admin') {
        return null
    }

    return (
        <AppLayout showExplorer={false}>
            <div className="max-w-4xl mx-auto py-8 px-4 space-y-8">
                <header className="space-y-1">
                    <h1 className="text-2xl font-bold tracking-tight">Системные настройки LLM</h1>
                    <p className="text-sm text-muted-foreground">
                        Настройки провайдера и модели для всей системы. Доступно только администратору.
                        Playground вынесен в Профиль → отдельная вкладка.
                    </p>
                </header>
                <SystemLLMSettingsPanel />
            </div>
        </AppLayout>
    )
}
