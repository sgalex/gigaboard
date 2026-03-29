/**
 * Базовый URL API и Socket.IO.
 *
 * - Не задан `VITE_API_URL` (или пусто) — один origin с nginx (Docker / прод): REST через относительные пути,
 *   Socket.IO на `window.location.origin`.
 * - Задан явно — прямой backend (локальный dev на :8000, отдельный домен API и т.д.).
 *
 * В production, если в образ ошибочно зашит `http://localhost:8000`, а UI открыт с nginx (`:3000` и т.д.),
 * запросы уходят на закрытый порт хоста → «сетевая ошибка». В этом случае принудительно используем относительные URL.
 *
 * Страница по HTTPS, а в бандле `http://тот-же-хост/...` → Mixed Content. Сравниваем hostname без учёта регистра,
 * убираем кавычки из env. Возвращаем `window.location.origin` (явный https), чтобы axios не собирал `http://...`.
 */
function stripEnvQuotes(s: string): string {
    const t = s.trim()
    if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) {
        return t.slice(1, -1).trim()
    }
    return t
}

function sameHostHttpAsHttpsPage(apiUrl: URL, win: Window & typeof globalThis): boolean {
    return (
        win.location.protocol === 'https:' &&
        apiUrl.protocol === 'http:' &&
        apiUrl.hostname.toLowerCase() === win.location.hostname.toLowerCase()
    )
}

export function getViteApiBaseUrl(): string {
    const v = import.meta.env.VITE_API_URL
    if (v === undefined || v === null) {
        return ''
    }
    let trimmed = stripEnvQuotes(String(v))
    if (trimmed === '') {
        return ''
    }

    if (typeof window !== 'undefined') {
        try {
            const u = new URL(trimmed)
            if (sameHostHttpAsHttpsPage(u, window)) {
                return window.location.origin
            }
        } catch {
            /* ignore malformed URL */
        }
    }

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

    // Последняя линия: страница HTTPS, в env всё ещё http://тот же хост (например parse падал раньше)
    if (typeof window !== 'undefined' && window.location.protocol === 'https:' && trimmed.startsWith('http://')) {
        try {
            const u = new URL(trimmed)
            if (u.hostname.toLowerCase() === window.location.hostname.toLowerCase()) {
                return window.location.origin
            }
        } catch {
            /* ignore */
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
