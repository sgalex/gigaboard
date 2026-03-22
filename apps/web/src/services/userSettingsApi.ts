import { useAuthStore } from '@/store/authStore'

export type LLMProvider = 'gigachat' | 'external_openai_compat'

export interface GigaChatModelInfo {
    id: string
    name: string
    description?: string | null
}

export interface UserAISettings {
    user_id: string
    provider: LLMProvider
    gigachat_model?: string | null
    gigachat_scope?: string | null
    has_gigachat_api_key?: boolean
    external_base_url?: string | null
    external_default_model?: string | null
    external_timeout_seconds?: number | null
    temperature?: number | null
    max_tokens?: number | null
    has_external_api_key: boolean
    preferred_style?: Record<string, unknown> | null
    /** Переопределения MULTI_AGENT_* (те же ключи, что в env) */
    multi_agent_settings?: Record<string, unknown> | null
}

export interface UpdateUserAISettingsPayload {
    provider: LLMProvider
    gigachat_model?: string | null
    gigachat_scope?: string | null
    gigachat_api_key?: string | null
    external_base_url?: string | null
    external_default_model?: string | null
    external_timeout_seconds?: number | null
    external_api_key?: string | null
    temperature?: number | null
    max_tokens?: number | null
    preferred_style?: Record<string, unknown> | null
    multi_agent_settings?: Record<string, unknown> | null
}

export interface TestAISettingsResponse {
    ok: boolean
    provider: LLMProvider
    message: string
    details?: Record<string, unknown>
}

const API_BASE = '/api/v1/users/me'

function getAuthHeaders() {
    const token = useAuthStore.getState().token
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    }
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }
    return headers
}

export async function fetchUserAISettings(): Promise<UserAISettings> {
    const resp = await fetch(`${API_BASE}/ai-settings`, {
        method: 'GET',
        headers: getAuthHeaders(),
    })
    if (!resp.ok) {
        throw new Error('Не удалось загрузить AI-настройки пользователя')
    }
    return resp.json()
}

export async function updateUserAISettings(payload: UpdateUserAISettingsPayload): Promise<UserAISettings> {
    const resp = await fetch(`${API_BASE}/ai-settings`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    })
    if (!resp.ok) {
        const errorText = await resp.text()
        throw new Error(errorText || 'Не удалось сохранить AI-настройки')
    }
    return resp.json()
}

export async function testUserAISettings(payload: Partial<UpdateUserAISettingsPayload> = {}): Promise<TestAISettingsResponse> {
    const resp = await fetch(`${API_BASE}/ai-settings/test`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    })
    if (!resp.ok) {
        const errorText = await resp.text()
        throw new Error(errorText || 'Тест подключения к LLM не удался')
    }
    return resp.json()
}

export async function fetchGigaChatModels(): Promise<GigaChatModelInfo[]> {
    const resp = await fetch(`${API_BASE}/ai-settings/gigachat-models`, {
        method: 'GET',
        headers: getAuthHeaders(),
    })
    if (!resp.ok) {
        throw new Error('Не удалось загрузить список моделей GigaChat')
    }
    return resp.json()
}
