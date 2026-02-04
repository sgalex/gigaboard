import { useAuthStore } from '../store/authStore'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { authAPI } from '../services/api'

export const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
    const navigate = useNavigate()
    const { token, user, setUser } = useAuthStore()
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        const loadUser = async () => {
            if (!token) {
                navigate('/login')
                setIsLoading(false)
                return
            }

            // If we have token but no user data, fetch user
            if (token && !user) {
                try {
                    const response = await authAPI.getCurrentUser()
                    setUser(response.data)
                } catch (error) {
                    console.error('Failed to load user:', error)
                    // Token is invalid, redirect to login
                    useAuthStore.getState().logout()
                    navigate('/login')
                }
            }

            setIsLoading(false)
        }

        loadUser()
    }, [token, user, navigate, setUser])

    if (isLoading) {
        return (
            <div className="h-screen flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
                    <p className="text-muted-foreground">Загрузка...</p>
                </div>
            </div>
        )
    }

    return token && user ? <>{children}</> : null
}
