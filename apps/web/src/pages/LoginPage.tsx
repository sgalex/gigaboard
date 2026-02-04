import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock, Loader2, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { authAPI } from '../services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AuthLayout } from '@/components/AuthLayout'
import { notify } from '@/store/notificationStore'
import { getErrorMessage } from '@/lib/errors'

export const LoginPage = () => {
    const navigate = useNavigate()
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const { setUser, setToken } = useAuthStore()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setIsLoading(true)

        try {
            const response = await authAPI.login(email, password)
            const { access_token, user } = response.data

            setToken(access_token)
            setUser(user)

            notify.success('Вы вошли в систему', { title: 'Успешно' })

            navigate('/welcome')
        } catch (err: any) {
            const message = getErrorMessage(err, 'Неверный email или пароль')
            setError(message)
            notify.error(message, { title: 'Ошибка входа' })
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <AuthLayout
            title="С возвращением"
            subtitle="Войдите в свой аккаунт GigaBoard"
            footer={(
                <span>
                    Нет аккаунта?{' '}
                    <Link to="/register" className="font-medium text-primary hover:underline">
                        Зарегистрироваться
                    </Link>
                </span>
            )}
        >
            {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4" />
                    <span>{error}</span>
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                    <Label htmlFor="email" className="text-foreground/80">Email адрес</Label>
                    <div className="relative">
                        <Input
                            id="email"
                            type="email"
                            placeholder="name@company.com"
                            className="bg-background border-border pl-10 focus:ring-2 focus:ring-primary/20 transition-all"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            disabled={isLoading}
                            required
                        />
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    </div>
                </div>

                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <Label htmlFor="password" className="text-foreground/80">Пароль</Label>
                        <a href="#" className="text-xs font-medium text-primary hover:text-primary/80 transition-colors">
                            Забыли пароль?
                        </a>
                    </div>
                    <div className="relative">
                        <Input
                            id="password"
                            type="password"
                            placeholder="••••••••"
                            className="bg-background border-border pl-10 focus:ring-2 focus:ring-primary/20 transition-all"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            disabled={isLoading}
                            required
                        />
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    </div>
                </div>

                <Button
                    type="submit"
                    size="lg"
                    className="w-full rounded-xl shadow-lg shadow-primary/20 active:scale-[0.98]"
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Вход...
                        </>
                    ) : (
                        'Войти в систему'
                    )}
                </Button>
            </form>
        </AuthLayout>
    )
}
