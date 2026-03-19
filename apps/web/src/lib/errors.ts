import axios from 'axios'

type ErrorLike = {
    response?: {
        data?: {
            detail?: unknown
            message?: unknown
            error?: unknown
        }
        status?: number
    }
    message?: string
}

function detailToMessage(detail: unknown): string | null {
    if (!detail) return null
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
        return detail
            .map((item: any) => {
                if (typeof item === 'string') return item
                const loc = Array.isArray(item?.loc) ? item.loc.join('.') : null
                const msg = typeof item?.msg === 'string' ? item.msg : null
                if (loc && msg) return `${loc}: ${msg}`
                return msg || null
            })
            .filter(Boolean)
            .join(', ')
    }
    return null
}

export function getErrorMessage(error: unknown, fallback = 'Произошла ошибка'): string {
    const err = error as ErrorLike

    if (axios.isAxiosError(error)) {
        const detail = detailToMessage(err.response?.data?.detail)
        if (detail) return detail

        if (typeof err.response?.data?.message === 'string') return err.response.data.message
        if (typeof err.response?.data?.error === 'string') return err.response.data.error

        if (err.response?.status === 401) return 'Неверные учетные данные'
        if (err.response?.status === 403) return 'Недостаточно прав доступа'
        if (err.response?.status === 404) return 'Ресурс не найден'
    }

    if (typeof err?.message === 'string' && err.message.trim()) {
        return err.message
    }

    return fallback
}
