/**
 * Базовый URL API и Socket.IO.
 *
 * **Браузер:** всегда `window.location.origin` — запросы идут туда же, где открыт UI
 * (Vite проксирует `/api`, `/socket.io`, … на backend; nginx в prod — то же).
 * Явный `VITE_API_URL` на другой хост в `.env` для локальной разработки больше не переопределяет origin в браузере,
 * чтобы не было CORS/редиректов и потери `Authorization`.
 *
 * **Вне браузера** (редкие скрипты): `VITE_API_URL` или пустая строка / fallback.
 *
 * См. также `vite.config.ts` — `VITE_DEV_PROXY_TARGET` куда проксировать в dev.
 */
function stripEnvQuotes(s: string): string {
    const t = s.trim()
    if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) {
        return t.slice(1, -1).trim()
    }
    return t
}

/** База API только из env (без `window`) — для небраузерных сценариев. */
function getApiBaseUrlFromEnv(): string {
    const raw = import.meta.env.VITE_API_URL
    const trimmed = raw === undefined || raw === null ? '' : stripEnvQuotes(String(raw))
    return trimmed
}

/**
 * Базовый URL для axios и абсолютных URL.
 * В SPA в браузере — всегда origin страницы (тот же, что UI).
 */
export function getViteApiBaseUrl(): string {
    const win = typeof window !== 'undefined' ? window : undefined
    if (win) {
        return win.location.origin
    }
    const fromEnv = getApiBaseUrlFromEnv()
    if (fromEnv !== '') {
        return fromEnv
    }
    return ''
}

/** Origin для socket.io-client — совпадает с REST в браузере. */
export function getSocketIoUrl(): string {
    const win = typeof window !== 'undefined' ? window : undefined
    if (win) {
        return win.location.origin
    }
    const base = getViteApiBaseUrl()
    if (base) {
        return base
    }
    return 'http://localhost:8000'
}

/**
 * Общие опции socket.io-client (path совпадает с CombinedASGI в backend и location в nginx).
 * `timeout` — полный handshake; по умолчанию в клиенте 20s, при медленном прокси/Docker часто мало.
 */
export const SOCKET_IO_CLIENT_OPTIONS = {
    path: '/socket.io',
    transports: ['polling', 'websocket'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10,
    timeout: 45_000,
    autoConnect: true,
}

/** Подсказка при connect_error в dev (нет прокси /socket.io, backend не слушает). */
export function logSocketIoConnectError(scope: string, error: unknown): void {
    console.error(scope, error)
    if (import.meta.env.DEV) {
        console.warn(
            `[Socket.IO] URL: ${getSocketIoUrl()} — ` +
                'убедитесь, что Vite проксирует /socket.io (vite.config.ts, VITE_DEV_PROXY_TARGET), ' +
                'или что nginx отдаёт UI и API с одного origin.'
        )
    }
}
