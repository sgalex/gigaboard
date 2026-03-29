/**
 * Базовый URL API и Socket.IO.
 *
 * **Важно (Mixed Content):** пустой `baseURL` в axios + относительный путь `/api/...` в XHR разрешается
 * относительно document base URL. Если на странице есть `<base href="http://...">` (прокси, CMS, старый шаблон),
 * браузер соберёт **http://** даже при открытой **https://** вкладке → блокировка Mixed Content.
 * Поэтому при работе в браузере без явного внешнего API используем **абсолютный** `window.location.origin`.
 *
 * Явный `VITE_API_URL` (другой хост / только HTTP backend) — после проверок ниже.
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
    const win = typeof window !== 'undefined' ? window : undefined
    const raw = import.meta.env.VITE_API_URL
    const trimmedFromEnv =
        raw === undefined || raw === null ? '' : stripEnvQuotes(String(raw))

    // Нет явного API в env — тот же origin, что и SPA (nginx / Vite). Только абсолютный origin.
    if (trimmedFromEnv === '') {
        return win ? win.location.origin : ''
    }

    let trimmed = trimmedFromEnv

    if (win) {
        try {
            const u = new URL(trimmed)
            if (sameHostHttpAsHttpsPage(u, win)) {
                return win.location.origin
            }
        } catch {
            /* ignore malformed URL */
        }
    }

    if (win && import.meta.env.PROD) {
        try {
            const u = new URL(trimmed)
            const pageOrigin = win.location.origin
            if (
                u.origin !== pageOrigin &&
                (u.hostname === 'localhost' || u.hostname === '127.0.0.1')
            ) {
                // Образ с localhost:8000, UI на nginx :3000 / https на домене — ходим на origin страницы
                return win.location.origin
            }
        } catch {
            /* ignore malformed URL */
        }
    }

    if (win && win.location.protocol === 'https:' && trimmed.startsWith('http://')) {
        try {
            const u = new URL(trimmed)
            if (u.hostname.toLowerCase() === win.location.hostname.toLowerCase()) {
                return win.location.origin
            }
        } catch {
            /* ignore */
        }
    }

    return trimmed
}

/** Origin для socket.io-client — тот же базис, что и REST (см. getViteApiBaseUrl). */
export function getSocketIoUrl(): string {
    const base = getViteApiBaseUrl()
    if (base) {
        return base
    }
    return 'http://localhost:8000'
}
