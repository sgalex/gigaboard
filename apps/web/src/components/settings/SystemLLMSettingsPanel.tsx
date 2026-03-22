import { Fragment, useCallback, useEffect, useState } from 'react'
import { Trash2, CircleHelp, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
    fetchSystemLLMSettings,
    updateSystemLLMSettings,
    createLlmConfig,
    updateLlmConfig,
    deleteLlmConfig,
    setAgentLLMOverrides,
    testSystemLLMSettings,
    fetchAdminGigaChatModels,
    AGENT_KEYS,
    type SystemLLMSettingsResponse,
    type LLMConfigResponse,
    type LLMConfigCreate,
    type LLMConfigUpdate,
    type LLMProvider,
    type AgentRuntimeOptions,
    type GigaChatModelInfo,
} from '@/services/adminSystemLlMApi'

const DEFAULT_BASE_URL = 'https://api.openai.com/v1'
const ALLOWED_CONTEXT_LEVELS = new Set(['full', 'compact', 'minimal'])
const DEFAULT_TIMEOUTS: Record<string, number> = {
    planner: 30,
    discovery: 120,
    research: 120,
    structurizer: 90,
    analyst: 60,
    transform_codex: 90,
    widget_codex: 90,
    reporter: 60,
    validator: 30,
}
const DEFAULT_RETRIES: Record<string, number> = {
    planner: 1,
    reporter: 1,
    validator: 0,
    _default: 1,
}
const DEFAULT_LADDERS: Record<string, string[]> = {
    planner: ['full', 'compact', 'minimal'],
    reporter: ['full', 'compact'],
    validator: ['full', 'compact'],
    _default: ['full', 'compact'],
}
const DEFAULT_CONTEXT_BUDGETS: Record<string, { max_items: number; max_total_chars: number }> = {
    planner: { max_items: 35, max_total_chars: 120000 },
    analyst: { max_items: 30, max_total_chars: 100000 },
    reporter: { max_items: 40, max_total_chars: 120000 },
    discovery: { max_items: 20, max_total_chars: 90000 },
    research: { max_items: 20, max_total_chars: 100000 },
    structurizer: { max_items: 20, max_total_chars: 110000 },
    transform_codex: { max_items: 25, max_total_chars: 110000 },
    widget_codex: { max_items: 25, max_total_chars: 110000 },
    validator: { max_items: 25, max_total_chars: 100000 },
    _default: { max_items: 30, max_total_chars: 100000 },
}
const AGENT_RUNTIME_LIMITS = {
    timeoutMin: 1,
    timeoutMax: 1800,
    retriesMin: 0,
    retriesMax: 10,
    itemsMin: 1,
    itemsMax: 200,
    charsMin: 1000,
    charsMax: 500000,
}

type AgentRuntimeDraft = {
    timeout_sec: string
    max_retries: string
    context_ladder: string
    max_items: string
    max_total_chars: string
    task_overrides: AgentTaskOverrideDraft[]
}

type AgentTaskOverrideDraft = {
    id: string
    task_type: string
    timeout_sec: string
    max_retries: string
    context_ladder: string
    max_items: string
    max_total_chars: string
}

function emptyRuntimeDraft(): AgentRuntimeDraft {
    return {
        timeout_sec: '',
        max_retries: '',
        context_ladder: '',
        max_items: '',
        max_total_chars: '',
        task_overrides: [],
    }
}

function createTaskOverrideDraft(
    taskType = '',
    initial?: Partial<Omit<AgentTaskOverrideDraft, 'id' | 'task_type'>>
): AgentTaskOverrideDraft {
    return {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        task_type: taskType,
        timeout_sec: initial?.timeout_sec ?? '',
        max_retries: initial?.max_retries ?? '',
        context_ladder: initial?.context_ladder ?? '',
        max_items: initial?.max_items ?? '',
        max_total_chars: initial?.max_total_chars ?? '',
    }
}

const TASK_TYPES_BY_AGENT: Record<string, string[]> = {
    planner: ['create_plan', 'expand_step', 'revise_remaining', 'replan'],
    reporter: ['summarize'],
    validator: ['validate'],
    discovery: ['search'],
    research: ['fetch_url', 'analyze_source'],
    structurizer: ['extract_structure'],
    analyst: ['analyze'],
    transform_codex: ['generate_transform_code'],
    widget_codex: ['generate_widget_code'],
}

function hasTaskOverridesEnabled(agentKey: string): boolean {
    return (TASK_TYPES_BY_AGENT[agentKey]?.length ?? 0) > 1
}

function defaultRuntimeDraftForAgent(agentKey: string): AgentRuntimeDraft {
    const timeout = DEFAULT_TIMEOUTS[agentKey] ?? 60
    const retries = DEFAULT_RETRIES[agentKey] ?? DEFAULT_RETRIES._default
    const ladder = DEFAULT_LADDERS[agentKey] ?? DEFAULT_LADDERS._default
    const budget = DEFAULT_CONTEXT_BUDGETS[agentKey] ?? DEFAULT_CONTEXT_BUDGETS._default
    return {
        timeout_sec: String(timeout),
        max_retries: String(retries),
        context_ladder: ladder.join(', '),
        max_items: String(budget.max_items),
        max_total_chars: String(budget.max_total_chars),
        task_overrides: [],
    }
}

function runtimeOptionsToDraft(agentKey: string, options?: AgentRuntimeOptions | null): AgentRuntimeDraft {
    if (!options) return emptyRuntimeDraft()
    const taskOverrides = options.task_overrides ?? {}
    const taskRows = hasTaskOverridesEnabled(agentKey)
        ? Object.entries(taskOverrides).map(([taskType, row]) =>
              createTaskOverrideDraft(taskType, {
                  timeout_sec: row.timeout_sec != null ? String(row.timeout_sec) : '',
                  max_retries: row.max_retries != null ? String(row.max_retries) : '',
                  context_ladder: Array.isArray(row.context_ladder) ? row.context_ladder.join(', ') : '',
                  max_items: row.max_items != null ? String(row.max_items) : '',
                  max_total_chars: row.max_total_chars != null ? String(row.max_total_chars) : '',
              })
          )
        : []
    return {
        timeout_sec: options.timeout_sec != null ? String(options.timeout_sec) : '',
        max_retries: options.max_retries != null ? String(options.max_retries) : '',
        context_ladder: Array.isArray(options.context_ladder) ? options.context_ladder.join(', ') : '',
        max_items: options.max_items != null ? String(options.max_items) : '',
        max_total_chars: options.max_total_chars != null ? String(options.max_total_chars) : '',
        task_overrides: taskRows,
    }
}

function parseIntInRange(
    raw: string,
    options: {
        fieldLabel: string
        min: number
        max: number
    },
): number | undefined {
    const { fieldLabel, min, max } = options
    const v = raw.trim()
    if (!v) return undefined
    const num = Number(v)
    if (!Number.isInteger(num)) {
        throw new Error(`${fieldLabel}: ожидается целое число`)
    }
    if (num < min || num > max) {
        throw new Error(`${fieldLabel}: значение должно быть в диапазоне ${min}..${max}`)
    }
    return num
}

function normalizeContextLadder(raw: string): string[] | undefined {
    const v = raw.trim()
    if (!v) return undefined
    const levels = v
        .split(',')
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean)
    if (levels.length === 0) return undefined
    const invalid = levels.filter((lvl) => !ALLOWED_CONTEXT_LEVELS.has(lvl))
    if (invalid.length > 0) {
        throw new Error(
            `context_ladder: недопустимые уровни ${invalid.join(', ')}. Разрешено: full, compact, minimal`
        )
    }
    return levels
}

function draftToRuntimeOptions(agentKey: string, draft: AgentRuntimeDraft): AgentRuntimeOptions | undefined {
    const timeout_sec = parseIntInRange(draft.timeout_sec, {
        fieldLabel: 'timeout_sec',
        min: AGENT_RUNTIME_LIMITS.timeoutMin,
        max: AGENT_RUNTIME_LIMITS.timeoutMax,
    })
    const max_retries = parseIntInRange(draft.max_retries, {
        fieldLabel: 'max_retries',
        min: AGENT_RUNTIME_LIMITS.retriesMin,
        max: AGENT_RUNTIME_LIMITS.retriesMax,
    })
    const max_items = parseIntInRange(draft.max_items, {
        fieldLabel: 'max_items',
        min: AGENT_RUNTIME_LIMITS.itemsMin,
        max: AGENT_RUNTIME_LIMITS.itemsMax,
    })
    const max_total_chars = parseIntInRange(draft.max_total_chars, {
        fieldLabel: 'max_total_chars',
        min: AGENT_RUNTIME_LIMITS.charsMin,
        max: AGENT_RUNTIME_LIMITS.charsMax,
    })
    const context_ladder = normalizeContextLadder(draft.context_ladder)

    let task_overrides: AgentRuntimeOptions['task_overrides']
    if (hasTaskOverridesEnabled(agentKey) && draft.task_overrides.length > 0) {
        const outTaskOverrides: NonNullable<AgentRuntimeOptions['task_overrides']> = {}
        for (const row of draft.task_overrides) {
            const hasAnyOverrideValue = Boolean(
                row.timeout_sec.trim() ||
                    row.max_retries.trim() ||
                    row.context_ladder.trim() ||
                    row.max_items.trim() ||
                    row.max_total_chars.trim()
            )
            if (!hasAnyOverrideValue && !row.task_type.trim()) {
                continue
            }
            if (!row.task_type.trim()) {
                throw new Error('task_overrides: укажите task_type для каждой заполненной строки')
            }
            const rowTimeout = parseIntInRange(row.timeout_sec, {
                fieldLabel: `task_overrides.${row.task_type}.timeout_sec`,
                min: AGENT_RUNTIME_LIMITS.timeoutMin,
                max: AGENT_RUNTIME_LIMITS.timeoutMax,
            })
            const rowRetries = parseIntInRange(row.max_retries, {
                fieldLabel: `task_overrides.${row.task_type}.max_retries`,
                min: AGENT_RUNTIME_LIMITS.retriesMin,
                max: AGENT_RUNTIME_LIMITS.retriesMax,
            })
            const rowItems = parseIntInRange(row.max_items, {
                fieldLabel: `task_overrides.${row.task_type}.max_items`,
                min: AGENT_RUNTIME_LIMITS.itemsMin,
                max: AGENT_RUNTIME_LIMITS.itemsMax,
            })
            const rowChars = parseIntInRange(row.max_total_chars, {
                fieldLabel: `task_overrides.${row.task_type}.max_total_chars`,
                min: AGENT_RUNTIME_LIMITS.charsMin,
                max: AGENT_RUNTIME_LIMITS.charsMax,
            })
            const rowLadder = normalizeContextLadder(row.context_ladder)
            outTaskOverrides[row.task_type.trim()] = {
                ...(rowTimeout != null ? { timeout_sec: rowTimeout } : {}),
                ...(rowRetries != null ? { max_retries: rowRetries } : {}),
                ...(rowLadder != null ? { context_ladder: rowLadder } : {}),
                ...(rowItems != null ? { max_items: rowItems } : {}),
                ...(rowChars != null ? { max_total_chars: rowChars } : {}),
            }
        }
        if (Object.keys(outTaskOverrides).length > 0) {
            task_overrides = outTaskOverrides
        }
    }

    const out: AgentRuntimeOptions = {
        ...(timeout_sec != null ? { timeout_sec } : {}),
        ...(max_retries != null ? { max_retries } : {}),
        ...(context_ladder != null ? { context_ladder } : {}),
        ...(max_items != null ? { max_items } : {}),
        ...(max_total_chars != null ? { max_total_chars } : {}),
        ...(task_overrides != null ? { task_overrides } : {}),
    }
    return Object.keys(out).length > 0 ? out : undefined
}

export function SystemLLMSettingsPanel() {
    const [settings, setSettings] = useState<SystemLLMSettingsResponse | null>(null)
    const [configs, setConfigs] = useState<LLMConfigResponse[]>([])
    const [gigachatModels, setGigachatModels] = useState<GigaChatModelInfo[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // Модель: форма добавления/редактирования
    const [presetFormOpen, setPresetFormOpen] = useState(false)
    const [editingPresetId, setEditingPresetId] = useState<string | null>(null)
    const [presetForm, setPresetForm] = useState<LLMConfigCreate & { gigachat_api_key?: string; external_api_key?: string }>({
        name: '',
        provider: 'gigachat',
        sort_order: 0,
        gigachat_model: '',
        gigachat_scope: 'GIGACHAT_API_CORP',
        gigachat_api_key: '',
        external_base_url: DEFAULT_BASE_URL,
        external_default_model: 'gpt-4.1-mini',
        external_timeout_seconds: 60,
        external_api_key: '',
        temperature: 0.7,
        max_tokens: undefined,
    })

    // Модель по умолчанию и привязки
    const [defaultId, setDefaultId] = useState<string | null>(null)
    const [overrides, setOverrides] = useState<Record<string, string>>({}) // agent_key -> llm_config_id
    const [runtimeOverrides, setRuntimeOverrides] = useState<Record<string, AgentRuntimeDraft>>({})
    const [savingDefault, setSavingDefault] = useState(false)
    const [savingOverrides, setSavingOverrides] = useState(false)

    // Тест
    const [testingId, setTestingId] = useState<string | null>(null)
    const [testResult, setTestResult] = useState<string | null>(null)

    const updateTaskOverride = useCallback(
        (agentKey: string, rowId: string, patch: Partial<AgentTaskOverrideDraft>) => {
            setRuntimeOverrides((prev) => {
                const current = prev[agentKey] ?? defaultRuntimeDraftForAgent(agentKey)
                const nextRows = current.task_overrides.map((row) =>
                    row.id === rowId ? { ...row, ...patch } : row
                )
                return {
                    ...prev,
                    [agentKey]: { ...current, task_overrides: nextRows },
                }
            })
        },
        []
    )

    const addTaskOverrideRow = useCallback((agentKey: string) => {
        setRuntimeOverrides((prev) => {
            const current = prev[agentKey] ?? defaultRuntimeDraftForAgent(agentKey)
            const defaultTaskType = TASK_TYPES_BY_AGENT[agentKey]?.[0] ?? ''
            return {
                ...prev,
                [agentKey]: {
                    ...current,
                    task_overrides: [...current.task_overrides, createTaskOverrideDraft(defaultTaskType)],
                },
            }
        })
    }, [])

    const removeTaskOverrideRow = useCallback((agentKey: string, rowId: string) => {
        setRuntimeOverrides((prev) => {
            const current = prev[agentKey] ?? defaultRuntimeDraftForAgent(agentKey)
            return {
                ...prev,
                [agentKey]: {
                    ...current,
                    task_overrides: current.task_overrides.filter((row) => row.id !== rowId),
                },
            }
        })
    }, [])

    const load = useCallback(async () => {
        try {
            setIsLoading(true)
            setError(null)
            const [data, models] = await Promise.all([
                fetchSystemLLMSettings(),
                fetchAdminGigaChatModels().catch(() => []),
            ])
            setSettings(data)
            setConfigs(data.configs)
            setGigachatModels(models)
            setDefaultId(data.default_llm_config_id ?? null)
            const ov: Record<string, string> = {}
            const ro: Record<string, AgentRuntimeDraft> = {}
            for (const { key } of AGENT_KEYS) {
                ro[key] = defaultRuntimeDraftForAgent(key)
            }
            for (const o of data.agent_overrides) {
                ov[o.agent_key] = o.llm_config_id
                ro[o.agent_key] = runtimeOptionsToDraft(o.agent_key, o.runtime_options)
            }
            setOverrides(ov)
            setRuntimeOverrides(ro)
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Не удалось загрузить настройки')
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        load()
    }, [load])

    const handleSaveDefault = async () => {
        try {
            setSavingDefault(true)
            setError(null)
            const data = await updateSystemLLMSettings({ default_llm_config_id: defaultId ?? undefined })
            setSettings(data)
            setDefaultId(data.default_llm_config_id ?? null)
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Не удалось сохранить')
        } finally {
            setSavingDefault(false)
        }
    }

    const handleSaveOverrides = async () => {
        try {
            setSavingOverrides(true)
            setError(null)
            const list = Object.entries(overrides)
                .filter(([, id]) => id)
                .map(([agent_key, llm_config_id]) => ({
                    agent_key,
                    llm_config_id,
                    runtime_options: draftToRuntimeOptions(
                        agent_key,
                        runtimeOverrides[agent_key] ?? emptyRuntimeDraft()
                    ),
                }))
            const data = await setAgentLLMOverrides(list)
            const ov: Record<string, string> = {}
            const ro: Record<string, AgentRuntimeDraft> = {}
            for (const { key } of AGENT_KEYS) {
                ro[key] = defaultRuntimeDraftForAgent(key)
            }
            for (const o of data) {
                ov[o.agent_key] = o.llm_config_id
                ro[o.agent_key] = runtimeOptionsToDraft(o.agent_key, o.runtime_options)
            }
            setOverrides(ov)
            setRuntimeOverrides(ro)
            if (settings) setSettings({ ...settings, agent_overrides: data })
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Не удалось сохранить привязки')
        } finally {
            setSavingOverrides(false)
        }
    }

    const openAddPreset = () => {
        setEditingPresetId(null)
        setPresetForm({
            name: '',
            provider: 'gigachat',
            sort_order: configs.length,
            gigachat_model: '',
            gigachat_scope: 'GIGACHAT_API_CORP',
            gigachat_api_key: '',
            external_base_url: DEFAULT_BASE_URL,
            external_default_model: 'gpt-4.1-mini',
            external_timeout_seconds: 60,
            external_api_key: '',
            temperature: 0.7,
            max_tokens: undefined,
        })
        setPresetFormOpen(true)
    }

    const openEditPreset = (c: LLMConfigResponse) => {
        setEditingPresetId(c.id)
        setPresetForm({
            name: c.name,
            provider: c.provider,
            sort_order: c.sort_order,
            gigachat_model: c.gigachat_model ?? '',
            gigachat_scope: c.gigachat_scope ?? 'GIGACHAT_API_CORP',
            gigachat_api_key: '',
            external_base_url: c.external_base_url ?? DEFAULT_BASE_URL,
            external_default_model: c.external_default_model ?? 'gpt-4.1-mini',
            external_timeout_seconds: c.external_timeout_seconds ?? 60,
            external_api_key: '',
            temperature: c.temperature ?? 0.7,
            max_tokens: c.max_tokens ?? undefined,
        })
        setPresetFormOpen(true)
    }

    const handleSavePreset = async () => {
        try {
            setError(null)
            const payload: LLMConfigCreate = {
                name: presetForm.name.trim(),
                provider: presetForm.provider,
                sort_order: presetForm.sort_order,
                gigachat_model: presetForm.gigachat_model || null,
                gigachat_scope: presetForm.gigachat_scope || null,
                gigachat_api_key: presetForm.gigachat_api_key || null,
                external_base_url: presetForm.external_base_url || null,
                external_default_model: presetForm.external_default_model || null,
                external_timeout_seconds: presetForm.external_timeout_seconds
                    ? Number(presetForm.external_timeout_seconds)
                    : null,
                external_api_key: presetForm.external_api_key || null,
                temperature: presetForm.temperature != null ? Number(presetForm.temperature) : null,
                max_tokens: presetForm.max_tokens != null ? Number(presetForm.max_tokens) : null,
            }
            if (editingPresetId) {
                const updatePayload: LLMConfigUpdate = { ...payload }
                await updateLlmConfig(editingPresetId, updatePayload)
            } else {
                await createLlmConfig(payload)
            }
            setPresetFormOpen(false)
            await load()
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Не удалось сохранить модель')
        }
    }

    const handleDeletePreset = async (id: string) => {
        if (!confirm('Удалить эту модель?')) return
        try {
            setError(null)
            await deleteLlmConfig(id)
            await load()
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Не удалось удалить модель')
        }
    }

    const handleTestPreset = async (id: string) => {
        try {
            setTestingId(id)
            setTestResult(null)
            setError(null)
            const resp = await testSystemLLMSettings(id)
            setTestResult(resp.ok ? resp.message : `Ошибка: ${resp.message}`)
        } catch (e: unknown) {
            setTestResult(e instanceof Error ? e.message : 'Тест не удался')
        } finally {
            setTestingId(null)
        }
    }

    return (
        <div className="space-y-6">
            {error && (
                <div className="rounded-md bg-destructive/10 text-destructive px-4 py-2 text-sm">
                    {error}
                </div>
            )}

            <div className="space-y-6">
                    {isLoading && !settings ? (
                        <p className="text-sm text-muted-foreground">Загрузка...</p>
                    ) : (
                        <>
                            {/* Модели LLM */}
                            <section className="space-y-3">
                                <h3 className="font-semibold">Модели LLM</h3>
                                <p className="text-sm text-muted-foreground">
                                    Настройте перечень LLM (GigaChat, внешний API). Затем выберите модель по умолчанию и при необходимости привяжите модель к агенту.
                                </p>
                                {presetFormOpen ? (
                                    <div className="rounded-lg border p-4 space-y-3 bg-muted/20">
                                        <h4 className="font-medium">{editingPresetId ? 'Редактировать модель' : 'Новая модель'}</h4>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                            <div>
                                                <Label>Название</Label>
                                                <Input
                                                    value={presetForm.name}
                                                    onChange={(e) => setPresetForm((p) => ({ ...p, name: e.target.value }))}
                                                    placeholder="Например: GigaChat Prod"
                                                />
                                            </div>
                                            <div>
                                                <Label>Провайдер</Label>
                                                <select
                                                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                                                    value={presetForm.provider}
                                                    onChange={(e) =>
                                                        setPresetForm((p) => ({ ...p, provider: e.target.value as LLMProvider }))
                                                    }
                                                >
                                                    <option value="gigachat">GigaChat</option>
                                                    <option value="external_openai_compat">Внешний OpenAI-совместимый</option>
                                                </select>
                                            </div>
                                        </div>
                                        {presetForm.provider === 'gigachat' && (
                                            <>
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                    <div>
                                                        <Label>API-ключ GigaChat</Label>
                                                        <Input
                                                            type="password"
                                                            value={presetForm.gigachat_api_key ?? ''}
                                                            onChange={(e) =>
                                                                setPresetForm((p) => ({ ...p, gigachat_api_key: e.target.value }))
                                                            }
                                                            placeholder="Оставьте пустым, чтобы не менять (при редактировании)"
                                                        />
                                                    </div>
                                                    <div>
                                                        <Label>Модель</Label>
                                                        <select
                                                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                                                            value={presetForm.gigachat_model ?? ''}
                                                            onChange={(e) =>
                                                                setPresetForm((p) => ({ ...p, gigachat_model: e.target.value }))
                                                            }
                                                        >
                                                            <option value="">— Выберите —</option>
                                                            {gigachatModels.map((m) => (
                                                                <option key={m.id} value={m.id}>
                                                                    {m.name}
                                                                    {m.description ? ` — ${m.description}` : ''}
                                                                </option>
                                                            ))}
                                                        </select>
                                                    </div>
                                                    <div>
                                                        <Label>Scope</Label>
                                                        <select
                                                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                                                            value={presetForm.gigachat_scope ?? 'GIGACHAT_API_CORP'}
                                                            onChange={(e) =>
                                                                setPresetForm((p) => ({ ...p, gigachat_scope: e.target.value }))
                                                            }
                                                        >
                                                            <option value="GIGACHAT_API_CORP">GIGACHAT_API_CORP (корпоративный)</option>
                                                            <option value="GIGACHAT_API_PERS">GIGACHAT_API_PERS (персональный)</option>
                                                            <option value="GIGACHAT_API_B2B">GIGACHAT_API_B2B (B2B)</option>
                                                        </select>
                                                    </div>
                                                </div>
                                            </>
                                        )}
                                        {presetForm.provider === 'external_openai_compat' && (
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                <div>
                                                    <Label>Base URL</Label>
                                                    <Input
                                                        value={presetForm.external_base_url ?? ''}
                                                        onChange={(e) =>
                                                            setPresetForm((p) => ({ ...p, external_base_url: e.target.value }))
                                                        }
                                                    />
                                                </div>
                                                <div>
                                                    <Label>Модель</Label>
                                                    <Input
                                                        value={presetForm.external_default_model ?? ''}
                                                        onChange={(e) =>
                                                            setPresetForm((p) => ({ ...p, external_default_model: e.target.value }))
                                                        }
                                                    />
                                                </div>
                                                <div>
                                                    <Label>Таймаут (с)</Label>
                                                    <Input
                                                        type="number"
                                                        value={presetForm.external_timeout_seconds ?? ''}
                                                        onChange={(e) =>
                                                            setPresetForm((p) => ({
                                                                ...p,
                                                                external_timeout_seconds: e.target.value ? Number(e.target.value) : undefined,
                                                            }))
                                                        }
                                                    />
                                                </div>
                                                <div>
                                                    <Label>API-ключ</Label>
                                                    <Input
                                                        type="password"
                                                        value={presetForm.external_api_key ?? ''}
                                                        onChange={(e) =>
                                                            setPresetForm((p) => ({ ...p, external_api_key: e.target.value }))
                                                        }
                                                        placeholder="Оставьте пустым, чтобы не менять"
                                                    />
                                                </div>
                                            </div>
                                        )}
                                        <div className="flex gap-2">
                                            <div>
                                                <Label>Temperature</Label>
                                                <Input
                                                    type="number"
                                                    step="0.1"
                                                    min="0"
                                                    max="1"
                                                    value={presetForm.temperature ?? ''}
                                                    onChange={(e) =>
                                                        setPresetForm((p) => ({
                                                            ...p,
                                                            temperature: e.target.value ? Number(e.target.value) : undefined,
                                                        }))
                                                    }
                                                />
                                            </div>
                                            <div>
                                                <Label>Max tokens</Label>
                                                <Input
                                                    type="number"
                                                    value={presetForm.max_tokens ?? ''}
                                                    onChange={(e) =>
                                                        setPresetForm((p) => ({
                                                            ...p,
                                                            max_tokens: e.target.value ? Number(e.target.value) : undefined,
                                                        }))
                                                    }
                                                    placeholder="по умолчанию"
                                                />
                                            </div>
                                        </div>
                                        <div className="flex gap-2">
                                            <Button onClick={handleSavePreset} disabled={!presetForm.name.trim()}>
                                                {editingPresetId ? 'Сохранить' : 'Создать модель'}
                                            </Button>
                                            <Button variant="outline" onClick={() => setPresetFormOpen(false)}>
                                                Отмена
                                            </Button>
                                        </div>
                                    </div>
                                ) : (
                                    <Button variant="outline" onClick={openAddPreset}>
                                        Добавить модель
                                    </Button>
                                )}
                                <ul className="space-y-2">
                                    {configs.map((c) => (
                                        <li
                                            key={c.id}
                                            className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                                        >
                                            <span>
                                                {c.name}
                                                {defaultId === c.id && (
                                                    <span className="ml-2 text-xs text-muted-foreground">(по умолчанию)</span>
                                                )}
                                                <span className="ml-2 text-muted-foreground">— {c.provider}</span>
                                            </span>
                                            <div className="flex gap-2">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => handleTestPreset(c.id)}
                                                    disabled={testingId !== null}
                                                >
                                                    {testingId === c.id ? 'Проверка...' : 'Тест'}
                                                </Button>
                                                <Button size="sm" variant="outline" onClick={() => openEditPreset(c)}>
                                                    Изменить
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="destructive"
                                                    onClick={() => handleDeletePreset(c.id)}
                                                >
                                                    Удалить
                                                </Button>
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                                {testResult && (
                                    <p className="text-sm text-muted-foreground">{testResult}</p>
                                )}
                            </section>

                            {/* Модель по умолчанию */}
                            <section className="space-y-2">
                                <h3 className="font-semibold">Модель по умолчанию</h3>
                                <p className="text-sm text-muted-foreground">
                                    Используется для всех агентов, у которых не задана своя привязка.
                                </p>
                                <div className="flex gap-2 items-center">
                                    <select
                                        className="flex h-9 min-w-[200px] rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                                        value={defaultId ?? ''}
                                        onChange={(e) => setDefaultId(e.target.value || null)}
                                    >
                                        <option value="">— Не выбрано —</option>
                                        {configs.map((c) => (
                                            <option key={c.id} value={c.id}>
                                                {c.name}
                                            </option>
                                        ))}
                                    </select>
                                    <Button onClick={handleSaveDefault} disabled={savingDefault}>
                                        {savingDefault ? 'Сохранение...' : 'Сохранить'}
                                    </Button>
                                </div>
                            </section>

                            {/* Привязки агентов */}
                            <section className="space-y-2">
                                <h3 className="font-semibold">Привязки агентов</h3>
                                <p className="text-sm text-muted-foreground">
                                    Для каждого агента можно выбрать модель из списка. Если не выбрана — используется модель по умолчанию.
                                </p>
                                <div className="rounded-md border overflow-hidden">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="border-b bg-muted/30">
                                                <th className="text-left p-2">Агент</th>
                                                <th className="text-left p-2">Модель</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {AGENT_KEYS.map(({ key, label }) => (
                                                <Fragment key={key}>
                                                    <tr className="border-b">
                                                        <td className="p-2 align-top">{label}</td>
                                                        <td className="p-2">
                                                            <select
                                                                className="flex h-8 w-full max-w-xs rounded-md border border-input bg-transparent px-2 py-1 text-sm"
                                                                value={overrides[key] ?? ''}
                                                                onChange={(e) =>
                                                                    setOverrides((prev) => ({
                                                                        ...prev,
                                                                        [key]: e.target.value || '',
                                                                    }))
                                                                }
                                                            >
                                                                <option value="">По умолчанию</option>
                                                                {configs.map((c) => (
                                                                    <option key={c.id} value={c.id}>
                                                                        {c.name}
                                                                    </option>
                                                                ))}
                                                            </select>
                                                        </td>
                                                    </tr>
                                                    <tr className="border-b bg-muted/10">
                                                        <td className="p-2 text-xs text-muted-foreground">Runtime policy</td>
                                                        <td className="p-2">
                                                            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                                                                <div className="space-y-1">
                                                                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                                                        <span>timeout_sec</span>
                                                                        <CircleHelp
                                                                            className="h-3.5 w-3.5"
                                                                            title="Таймаут выполнения шага в секундах. Диапазон: 1..1800."
                                                                        />
                                                                    </div>
                                                                    <Input
                                                                        placeholder="timeout"
                                                                        value={runtimeOverrides[key]?.timeout_sec ?? ''}
                                                                        onChange={(e) =>
                                                                            setRuntimeOverrides((prev) => ({
                                                                                ...prev,
                                                                                [key]: {
                                                                                    ...(prev[key] ?? emptyRuntimeDraft()),
                                                                                    timeout_sec: e.target.value,
                                                                                },
                                                                            }))
                                                                        }
                                                                    />
                                                                </div>
                                                                <div className="space-y-1">
                                                                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                                                        <span>max_retries</span>
                                                                        <CircleHelp
                                                                            className="h-3.5 w-3.5"
                                                                            title="Сколько раз повторять шаг при ошибке. Диапазон: 0..10."
                                                                        />
                                                                    </div>
                                                                    <Input
                                                                        placeholder="retries"
                                                                        value={runtimeOverrides[key]?.max_retries ?? ''}
                                                                        onChange={(e) =>
                                                                            setRuntimeOverrides((prev) => ({
                                                                                ...prev,
                                                                                [key]: {
                                                                                    ...(prev[key] ?? emptyRuntimeDraft()),
                                                                                    max_retries: e.target.value,
                                                                                },
                                                                            }))
                                                                        }
                                                                    />
                                                                </div>
                                                                <div className="space-y-1">
                                                                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                                                        <span>context_ladder</span>
                                                                        <CircleHelp
                                                                            className="h-3.5 w-3.5"
                                                                            title="Уровни деградации контекста через запятую. Разрешено: full, compact, minimal."
                                                                        />
                                                                    </div>
                                                                    <Input
                                                                        placeholder="full,compact,minimal"
                                                                        value={runtimeOverrides[key]?.context_ladder ?? ''}
                                                                        onChange={(e) =>
                                                                            setRuntimeOverrides((prev) => ({
                                                                                ...prev,
                                                                                [key]: {
                                                                                    ...(prev[key] ?? emptyRuntimeDraft()),
                                                                                    context_ladder: e.target.value,
                                                                                },
                                                                            }))
                                                                        }
                                                                    />
                                                                </div>
                                                                <div className="space-y-1">
                                                                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                                                        <span>max_items</span>
                                                                        <CircleHelp
                                                                            className="h-3.5 w-3.5"
                                                                            title="Максимум элементов agent_results в prompt. Диапазон: 1..200."
                                                                        />
                                                                    </div>
                                                                    <Input
                                                                        placeholder="max_items"
                                                                        value={runtimeOverrides[key]?.max_items ?? ''}
                                                                        onChange={(e) =>
                                                                            setRuntimeOverrides((prev) => ({
                                                                                ...prev,
                                                                                [key]: {
                                                                                    ...(prev[key] ?? emptyRuntimeDraft()),
                                                                                    max_items: e.target.value,
                                                                                },
                                                                            }))
                                                                        }
                                                                    />
                                                                </div>
                                                                <div className="space-y-1">
                                                                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                                                        <span>max_total_chars</span>
                                                                        <CircleHelp
                                                                            className="h-3.5 w-3.5"
                                                                            title="Ограничение общего размера контекста в символах. Диапазон: 1000..500000."
                                                                        />
                                                                    </div>
                                                                    <Input
                                                                        placeholder="max_total_chars"
                                                                        value={runtimeOverrides[key]?.max_total_chars ?? ''}
                                                                        onChange={(e) =>
                                                                            setRuntimeOverrides((prev) => ({
                                                                                ...prev,
                                                                                [key]: {
                                                                                    ...(prev[key] ?? emptyRuntimeDraft()),
                                                                                    max_total_chars: e.target.value,
                                                                                },
                                                                            }))
                                                                        }
                                                                    />
                                                                </div>
                                                            </div>
                                                            {hasTaskOverridesEnabled(key) ? (
                                                                <>
                                                                    <div className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
                                                                        <span>task_overrides</span>
                                                                        <CircleHelp
                                                                            className="h-3.5 w-3.5"
                                                                            title="Отдельные правила для task_type. Добавьте строку, выберите задачу и задайте значения override."
                                                                        />
                                                                    </div>
                                                                    <div className="mt-1 space-y-2">
                                                                        {(runtimeOverrides[key]?.task_overrides ?? []).map((row) => (
                                                                            <div
                                                                                key={row.id}
                                                                                className="rounded-md border p-2 bg-background/70 space-y-2"
                                                                            >
                                                                                <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
                                                                                    <select
                                                                                        className="flex h-8 w-full rounded-md border border-input bg-transparent px-2 py-1 text-xs md:col-span-2"
                                                                                        value={row.task_type}
                                                                                        onChange={(e) =>
                                                                                            updateTaskOverride(key, row.id, {
                                                                                                task_type: e.target.value,
                                                                                            })
                                                                                        }
                                                                                    >
                                                                                        <option value="">Выберите task_type</option>
                                                                                        {(TASK_TYPES_BY_AGENT[key] ?? []).map((task) => (
                                                                                            <option key={task} value={task}>
                                                                                                {task}
                                                                                            </option>
                                                                                        ))}
                                                                                    </select>
                                                                                    <Input
                                                                                        className="h-8 text-xs"
                                                                                        placeholder="timeout"
                                                                                        value={row.timeout_sec}
                                                                                        onChange={(e) =>
                                                                                            updateTaskOverride(key, row.id, {
                                                                                                timeout_sec: e.target.value,
                                                                                            })
                                                                                        }
                                                                                    />
                                                                                    <Input
                                                                                        className="h-8 text-xs"
                                                                                        placeholder="retries"
                                                                                        value={row.max_retries}
                                                                                        onChange={(e) =>
                                                                                            updateTaskOverride(key, row.id, {
                                                                                                max_retries: e.target.value,
                                                                                            })
                                                                                        }
                                                                                    />
                                                                                    <Input
                                                                                        className="h-8 text-xs"
                                                                                        placeholder="ladder"
                                                                                        value={row.context_ladder}
                                                                                        onChange={(e) =>
                                                                                            updateTaskOverride(key, row.id, {
                                                                                                context_ladder: e.target.value,
                                                                                            })
                                                                                        }
                                                                                    />
                                                                                    <Input
                                                                                        className="h-8 text-xs"
                                                                                        placeholder="max_items"
                                                                                        value={row.max_items}
                                                                                        onChange={(e) =>
                                                                                            updateTaskOverride(key, row.id, {
                                                                                                max_items: e.target.value,
                                                                                            })
                                                                                        }
                                                                                    />
                                                                                    <div className="flex items-center gap-2">
                                                                                        <Input
                                                                                            className="h-8 text-xs"
                                                                                            placeholder="max_total_chars"
                                                                                            value={row.max_total_chars}
                                                                                            onChange={(e) =>
                                                                                                updateTaskOverride(key, row.id, {
                                                                                                    max_total_chars: e.target.value,
                                                                                                })
                                                                                            }
                                                                                        />
                                                                                        <Button
                                                                                            type="button"
                                                                                            variant="ghost"
                                                                                            size="icon"
                                                                                            className="h-8 w-8"
                                                                                            onClick={() => removeTaskOverrideRow(key, row.id)}
                                                                                            title="Удалить override"
                                                                                        >
                                                                                            <Trash2 className="h-4 w-4" />
                                                                                        </Button>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                        ))}
                                                                        <Button
                                                                            type="button"
                                                                            variant="outline"
                                                                            size="sm"
                                                                            className="h-8"
                                                                            onClick={() => addTaskOverrideRow(key)}
                                                                        >
                                                                            <Plus className="h-3.5 w-3.5 mr-1" />
                                                                            Добавить override
                                                                        </Button>
                                                                    </div>
                                                                </>
                                                            ) : (
                                                                <p className="mt-2 text-[11px] text-muted-foreground">
                                                                    Для этого агента task override не нужен: используется один тип задачи
                                                                    ({TASK_TYPES_BY_AGENT[key]?.[0] ?? 'default'}).
                                                                </p>
                                                            )}
                                                        </td>
                                                    </tr>
                                                </Fragment>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                                <Button onClick={handleSaveOverrides} disabled={savingOverrides}>
                                    {savingOverrides ? 'Сохранение...' : 'Сохранить привязки'}
                                </Button>
                            </section>
                        </>
                    )}
            </div>
        </div>
    )
}
