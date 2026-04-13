import { useAuthStore } from '@/store/authStore'

export type LLMProvider = 'gigachat' | 'external_openai_compat'

export interface GigaChatModelInfo {
    id: string
    name: string
    description?: string | null
}

export interface LLMConfigResponse {
    id: string
    name: string
    provider: LLMProvider
    sort_order: number
    gigachat_model?: string | null
    gigachat_scope?: string | null
    has_gigachat_api_key: boolean
    external_base_url?: string | null
    external_default_model?: string | null
    external_timeout_seconds?: number | null
    has_external_api_key: boolean
    temperature?: number | null
    max_tokens?: number | null
}

export interface LLMConfigCreate {
    name: string
    provider?: LLMProvider
    sort_order?: number
    gigachat_model?: string | null
    gigachat_scope?: string | null
    gigachat_api_key?: string | null
    external_base_url?: string | null
    external_default_model?: string | null
    external_timeout_seconds?: number | null
    external_api_key?: string | null
    temperature?: number | null
    max_tokens?: number | null
}

export interface LLMConfigUpdate {
    name?: string
    provider?: LLMProvider
    sort_order?: number
    gigachat_model?: string | null
    gigachat_scope?: string | null
    gigachat_api_key?: string | null
    external_base_url?: string | null
    external_default_model?: string | null
    external_timeout_seconds?: number | null
    external_api_key?: string | null
    temperature?: number | null
    max_tokens?: number | null
}

export interface SystemLLMSettingsResponse {
    default_llm_config_id: string | null
    configs: LLMConfigResponse[]
    agent_overrides: AgentLLMOverrideItem[]
}

export interface SystemLLMSettingsUpdate {
    default_llm_config_id?: string | null
}

export interface AgentRuntimeTaskOptions {
    timeout_sec?: number
    max_retries?: number
    context_ladder?: string[]
    max_items?: number
    max_total_chars?: number
}

export interface AgentRuntimeOptions extends AgentRuntimeTaskOptions {
    task_overrides?: Record<string, AgentRuntimeTaskOptions>
}

export interface AgentLLMOverrideItem {
    agent_key: string
    llm_config_id: string
    runtime_options?: AgentRuntimeOptions | null
}

export interface TestSystemLLMResponse {
    ok: boolean
    provider: LLMProvider
    message: string
    details?: Record<string, unknown>
}

const API_BASE = '/api/v1/admin'

function getAuthHeaders(): HeadersInit {
    const token = useAuthStore.getState().token
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    }
    if (token) {
        ;(headers as Record<string, string>)['Authorization'] = `Bearer ${token}`
    }
    return headers
}

export async function fetchSystemLLMSettings(): Promise<SystemLLMSettingsResponse> {
    const resp = await fetch(`${API_BASE}/llm-settings`, {
        method: 'GET',
        headers: getAuthHeaders(),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        throw new Error('Не удалось загрузить системные настройки LLM')
    }
    return resp.json()
}

export async function updateSystemLLMSettings(
    payload: SystemLLMSettingsUpdate
): Promise<SystemLLMSettingsResponse> {
    const resp = await fetch(`${API_BASE}/llm-settings`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        const errorText = await resp.text()
        throw new Error(errorText || 'Не удалось сохранить настройки')
    }
    return resp.json()
}

export async function fetchLlmConfigs(): Promise<LLMConfigResponse[]> {
    const resp = await fetch(`${API_BASE}/llm-configs`, {
        method: 'GET',
        headers: getAuthHeaders(),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        throw new Error('Не удалось загрузить список моделей')
    }
    return resp.json()
}

export async function createLlmConfig(
    payload: LLMConfigCreate
): Promise<LLMConfigResponse> {
    const resp = await fetch(`${API_BASE}/llm-configs`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        const errorText = await resp.text()
        throw new Error(errorText || 'Не удалось создать модель')
    }
    return resp.json()
}

export async function updateLlmConfig(
    id: string,
    payload: LLMConfigUpdate
): Promise<LLMConfigResponse> {
    const resp = await fetch(`${API_BASE}/llm-configs/${id}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        const errorText = await resp.text()
        throw new Error(errorText || 'Не удалось обновить модель')
    }
    return resp.json()
}

export async function deleteLlmConfig(id: string): Promise<void> {
    const resp = await fetch(`${API_BASE}/llm-configs/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        const data = await resp.json().catch(() => ({}))
        throw new Error((data as { detail?: string }).detail || 'Не удалось удалить модель')
    }
}

export async function fetchAgentLLMOverrides(): Promise<AgentLLMOverrideItem[]> {
    const resp = await fetch(`${API_BASE}/agent-llm-overrides`, {
        method: 'GET',
        headers: getAuthHeaders(),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        throw new Error('Не удалось загрузить привязки агентов')
    }
    return resp.json()
}

export async function setAgentLLMOverrides(
    overrides: AgentLLMOverrideItem[]
): Promise<AgentLLMOverrideItem[]> {
    const resp = await fetch(`${API_BASE}/agent-llm-overrides`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ overrides }),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        const errorText = await resp.text()
        throw new Error(errorText || 'Не удалось сохранить привязки')
    }
    return resp.json()
}

export async function testSystemLLMSettings(
    llmConfigId?: string | null
): Promise<TestSystemLLMResponse> {
    const url = new URL(`${API_BASE}/llm-settings/test`, window.location.origin)
    if (llmConfigId) url.searchParams.set('llm_config_id', llmConfigId)
    const resp = await fetch(url.toString(), {
        method: 'POST',
        headers: getAuthHeaders(),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        const errorText = await resp.text()
        throw new Error(errorText || 'Тест не удался')
    }
    return resp.json()
}

export async function fetchAdminGigaChatModels(): Promise<GigaChatModelInfo[]> {
    const resp = await fetch(`${API_BASE}/llm-settings/gigachat-models`, {
        method: 'GET',
        headers: getAuthHeaders(),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        throw new Error('Не удалось загрузить список моделей')
    }
    return resp.json()
}

export interface PlaygroundChatMessage {
    role: 'user' | 'assistant'
    content: string
}

type PlaygroundStreamEvent = {
    type: 'start' | 'progress' | 'plan' | 'result' | 'error' | 'done'
    agent_label?: string
    task?: string
    steps?: string[]
    completed_count?: number
    source?: string
    result?: Record<string, unknown>
    error?: string
}

export interface RunPlaygroundStreamHandlers {
    onProgress?: (
        agentLabel: string,
        task: string,
        meta?: {
            phase?: string
            stepIndex?: number
            totalSteps?: number
        }
    ) => void
    onPlanUpdate?: (
        steps: string[],
        meta?: {
            completedCount?: number
            source?: string
        }
    ) => void
    onResult?: (result: Record<string, unknown>) => void
    onError?: (error: string) => void
}

export async function runPlayground(
    prompt: string,
    chatHistory?: PlaygroundChatMessage[],
): Promise<Record<string, unknown>> {
    const resp = await fetch(`${API_BASE}/llm-playground/run`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
            prompt,
            chat_history: chatHistory && chatHistory.length > 0 ? chatHistory : undefined,
        }),
    })
    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        if (resp.status === 503) throw new Error('Orchestrator недоступен (Redis или GigaChat не настроены)')
        const errorText = await resp.text()
        throw new Error(errorText || 'Запуск Playground не удался')
    }
    return resp.json()
}

export async function runPlaygroundStream(
    prompt: string,
    chatHistory: PlaygroundChatMessage[] | undefined,
    handlers: RunPlaygroundStreamHandlers
): Promise<void> {
    const resp = await fetch(`${API_BASE}/llm-playground/run-stream`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
            prompt,
            chat_history: chatHistory && chatHistory.length > 0 ? chatHistory : undefined,
        }),
    })

    if (!resp.ok) {
        if (resp.status === 403) throw new Error('Доступ только для администратора')
        if (resp.status === 503) throw new Error('Orchestrator недоступен (Redis или GigaChat не настроены)')
        const errorText = await resp.text()
        throw new Error(errorText || 'Запуск Playground не удался')
    }

    if (!resp.body) {
        throw new Error('Пустой поток ответа от Playground')
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue

            let event: PlaygroundStreamEvent
            try {
                event = JSON.parse(trimmed) as PlaygroundStreamEvent
            } catch {
                continue
            }

            if (event.type === 'progress') {
                handlers.onProgress?.(
                    event.agent_label || 'Агент',
                    event.task || 'Выполнение шага',
                    {
                        phase: typeof (event as Record<string, unknown>).phase === 'string'
                            ? ((event as Record<string, unknown>).phase as string)
                            : undefined,
                        stepIndex: typeof (event as Record<string, unknown>).step_index === 'number'
                            ? ((event as Record<string, unknown>).step_index as number)
                            : undefined,
                        totalSteps: typeof (event as Record<string, unknown>).total_steps === 'number'
                            ? ((event as Record<string, unknown>).total_steps as number)
                            : undefined,
                    }
                )
            } else if (event.type === 'plan') {
                handlers.onPlanUpdate?.(
                    Array.isArray(event.steps) ? event.steps : [],
                    {
                        completedCount:
                            typeof event.completed_count === 'number' ? event.completed_count : undefined,
                        source: typeof event.source === 'string' ? event.source : undefined,
                    }
                )
            } else if (event.type === 'result' && event.result) {
                handlers.onResult?.(event.result)
            } else if (event.type === 'error') {
                handlers.onError?.(event.error || 'Запуск Playground не удался')
            }
        }
    }
}

export const AGENT_KEYS = [
    { key: 'planner', label: 'Планировщик' },
    { key: 'discovery', label: 'Поиск' },
    { key: 'research', label: 'Исследование' },
    { key: 'structurizer', label: 'Структуризатор' },
    { key: 'analyst', label: 'Аналитик' },
    { key: 'transform_codex', label: 'Код трансформаций' },
    { key: 'widget_codex', label: 'Код виджетов' },
    { key: 'reporter', label: 'Реporter' },
    { key: 'validator', label: 'Валидатор' },
    {
        key: 'context_graph_compression',
        label: 'Сжатие контекста (граф L1/L2)',
    },
] as const
