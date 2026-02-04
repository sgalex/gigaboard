import { create } from 'zustand'

export type NotificationType = 'success' | 'error' | 'info'

export interface NotificationToast {
    id: string
    type: NotificationType
    title?: string
    message: string
    createdAt: number
    durationMs: number
}

interface NotificationState {
    toasts: NotificationToast[]
    show: (toast: {
        type: NotificationType
        title?: string
        message: string
        durationMs?: number
    }) => string
    dismiss: (id: string) => void
    clear: () => void
}

const createId = () => `${Date.now()}_${Math.random().toString(16).slice(2)}`

export const useNotificationStore = create<NotificationState>((set, get) => ({
    toasts: [],
    show: (toast) => {
        const id = createId()
        const item: NotificationToast = {
            id,
            createdAt: Date.now(),
            durationMs: toast.durationMs ?? 4500,
            type: toast.type,
            title: toast.title,
            message: toast.message,
        }

        set((state) => {
            const next = [item, ...state.toasts]
            return { toasts: next.slice(0, 5) }
        })

        return id
    },
    dismiss: (id) => {
        set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
    },
    clear: () => set({ toasts: [] }),
}))

export const notify = {
    success: (message: string, opts?: { title?: string; durationMs?: number }) =>
        useNotificationStore.getState().show({ type: 'success', message, ...opts }),
    error: (message: string, opts?: { title?: string; durationMs?: number }) =>
        useNotificationStore.getState().show({ type: 'error', message, ...opts }),
    info: (message: string, opts?: { title?: string; durationMs?: number }) =>
        useNotificationStore.getState().show({ type: 'info', message, ...opts }),
}
