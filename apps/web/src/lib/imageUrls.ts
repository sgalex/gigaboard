import { getViteApiBaseUrl } from '@/config/apiBase'

/** Сохраняемый путь превью: `/api/v1/files/image/{file_id}` — тот же origin, что у UI (см. `getViteApiBaseUrl`). */
export function getFileImageUrl(fileId: string): string {
    const base = getViteApiBaseUrl().replace(/\/$/, '')
    return `${base}/api/v1/files/image/${fileId}`
}

/**
 * Same-origin URL для `<img src>`: относительный API-путь или абсолютный URL только на `/api/v1/files/image/…`.
 * Иначе `null` — используйте `?? url`.
 */
export function getProxiedImageUrl(url: string | null | undefined): string | null {
    if (url == null || url === '') return null
    const trimmed = url.trim()
    const origin = getViteApiBaseUrl().replace(/\/$/, '')
    if (!origin) return null
    if (trimmed.startsWith('/')) {
        return `${origin}${trimmed}`
    }
    try {
        const u = new URL(trimmed)
        if (u.pathname.startsWith('/api/v1/files/image/')) {
            return `${origin}${u.pathname}${u.search}`
        }
    } catch {
        /* invalid absolute URL */
    }
    return null
}
