import { create } from 'zustand'

interface AuthState {
    user: {
        id: string
        email: string
        username: string
        role?: string // "user" | "admin"
        created_at: string
        updated_at: string
    } | null
    token: string | null
    isLoading: boolean
    error: string | null
    setUser: (user: any) => void
    setToken: (token: string) => void
    setIsLoading: (loading: boolean) => void
    setError: (error: string | null) => void
    logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    token: localStorage.getItem('token'),
    isLoading: false,
    error: null,
    setUser: (user) => set({ user }),
    setToken: (token) => {
        localStorage.setItem('token', token)
        set({ token })
    },
    setIsLoading: (loading) => set({ isLoading: loading }),
    setError: (error) => set({ error }),
    logout: () => {
        localStorage.removeItem('token')
        set({ user: null, token: null })
    },
}))
