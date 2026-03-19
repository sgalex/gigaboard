/**
 * Базовый URL API и Socket.IO.
 *
 * - Не задан `VITE_API_URL` (или пусто) — один origin с nginx (Docker / прод): REST через относительные пути,
 *   Socket.IO на `window.location.origin`.
 * - Задан явно — прямой backend (локальный dev на :8000, отдельный домен API и т.д.).
 *
 * В production, если в образ ошибочно зашит `http://localhost:8000`, а UI открыт с nginx (`:3000` и т.д.),
 * запросы уходят на закрытый порт хоста → «сетевая ошибка». В этом случае принудительно используем относительные URL.
 */
export function getViteApiBaseUrl(): string {
    const v = import.meta.env.VITE_API_URL
    if (v === undefined || v === null || String(v).trim() === '') {
        return ''
    }
    let trimmed = String(v).trim()

    if (typeof window !== 'undefined' && import.meta.env.PROD) {
        try {
            const u = new URL(trimmed)
            const pageOrigin = window.location.origin
            if (
                u.origin !== pageOrigin &&
                (u.hostname === 'localhost' || u.hostname === '127.0.0.1')
            ) {
                return ''
            }
        } catch {
            /* ignore malformed URL */
        }
    }

    return trimmed
}

/** Origin для socket.io-client (пустой env → текущий хост страницы). */
export function getSocketIoUrl(): string {
    const base = getViteApiBaseUrl()
    if (base) {
        return base
    }
    if (typeof window !== 'undefined') {
        return window.location.origin
    }
    return 'http://localhost:8000'
}
