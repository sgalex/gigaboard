import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock, User, Loader2, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { authAPI } from '../services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AuthLayout } from '@/components/AuthLayout'
import { notify } from '@/store/notificationStore'
import { getErrorMessage } from '@/lib/errors'

export const RegisterPage = () => {
    const navigate = useNavigate()
    const [email, setEmail] = useState('')
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [error, setError] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const { setUser, setToken } = useAuthStore()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')

        if (password !== confirmPassword) {
            const message = 'Пароли не совпадают'
            setError(message)
            notify.error(message, { title: 'Проверьте данные' })
            return
        }

        if (password.length < 8) {
            const message = 'Пароль должен быть не менее 8 символов'
            setError(message)
            notify.error(message, { title: 'Проверьте данные' })
            return
        }

        setIsLoading(true)

        try {
            const response = await authAPI.register(email, username, password)
            const { access_token, user } = response.data

            setToken(access_token)
            setUser(user)

            notify.success('Аккаунт создан', { title: 'Успешно' })

            navigate('/welcome')
        } catch (err: any) {
            const message = getErrorMessage(err, 'Ошибка регистрации')
            setError(message)
            notify.error(message, { title: 'Ошибка регистрации' })
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <AuthLayout
            title="Создать аккаунт"
            subtitle="Начните работу с GigaBoard сегодня"
            footer={(
                <span>
                    Уже есть аккаунт?{' '}
                    <Link to="/login" className="font-medium text-primary hover:underline">
                        Войти
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

            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="username" className="text-foreground/80">Имя пользователя</Label>
                    <div className="relative">
                        <Input
                            id="username"
                            type="text"
                            placeholder="ivan_ivanov"
                            className="bg-background border-border pl-10 focus:ring-2 focus:ring-primary/20 transition-all"
                            value={username}
                            onChange={(e: any) => setUsername(e.target.value)}
                            minLength={3}
                            disabled={isLoading}
                            required
                        />
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    </div>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="email" className="text-foreground/80">Email адрес</Label>
                    <div className="relative">
                        <Input
                            id="email"
                            type="email"
                            placeholder="name@company.com"
                            className="bg-background border-border pl-10 focus:ring-2 focus:ring-primary/20 transition-all"
                            value={email}
                            onChange={(e: any) => setEmail(e.target.value)}
                            disabled={isLoading}
                            required
                        />
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                        <Label htmlFor="password" title="Пароль" className="text-foreground/80">Пароль</Label>
                        <div className="relative">
                            <Input
                                id="password"
                                type="password"
                                placeholder="••••••••"
                                className="bg-background border-border pl-10 focus:ring-2 focus:ring-primary/20 transition-all"
                                value={password}
                                onChange={(e: any) => setPassword(e.target.value)}
                                minLength={8}
                                disabled={isLoading}
                                required
                            />
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="confirmPassword" title="Повторите" className="text-foreground/80">Повторите</Label>
                        <div className="relative">
                            <Input
                                id="confirmPassword"
                                type="password"
                                placeholder="••••••••"
                                className="bg-background border-border pl-10 focus:ring-2 focus:ring-primary/20 transition-all"
                                value={confirmPassword}
                                onChange={(e: any) => setConfirmPassword(e.target.value)}
                                disabled={isLoading}
                                required
                            />
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                        </div>
                    </div>
                </div>

                <div className="pt-2">
                    <Button
                        type="submit"
                        size="lg"
                        className="w-full rounded-xl shadow-lg shadow-primary/20 active:scale-[0.98]"
                        disabled={isLoading}
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Создание...
                            </>
                        ) : (
                            'Создать аккаунт'
                        )}
                    </Button>
                </div>
            </form>
        </AuthLayout>
    )
}
