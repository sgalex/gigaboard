import { useCallback, useEffect, useRef, useState } from 'react'
import { Send, Trash2, Sparkles, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
    fetchSystemLLMSettings,
    updateSystemLLMSettings,
    createLlmConfig,
    updateLlmConfig,
    deleteLlmConfig,
    setAgentLLMOverrides,
    testSystemLLMSettings,
    fetchAdminGigaChatModels,
    runPlayground,
    AGENT_KEYS,
    type SystemLLMSettingsResponse,
    type LLMConfigResponse,
    type LLMConfigCreate,
    type LLMConfigUpdate,
    type LLMProvider,
    type GigaChatModelInfo,
    type PlaygroundChatMessage,
} from '@/services/adminSystemLlMApi'

const DEFAULT_BASE_URL = 'https://api.openai.com/v1'

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
    const [savingDefault, setSavingDefault] = useState(false)
    const [savingOverrides, setSavingOverrides] = useState(false)

    // Тест
    const [testingId, setTestingId] = useState<string | null>(null)
    const [testResult, setTestResult] = useState<string | null>(null)

    // Playground (чат: история сообщений как в AI-ассистенте)
    type PlaygroundMessage = { id: string; role: 'user' | 'assistant'; content: string; raw?: Record<string, unknown> }
    const [playgroundMessages, setPlaygroundMessages] = useState<PlaygroundMessage[]>([])
    const [playgroundInput, setPlaygroundInput] = useState('')
    const [playgroundRunning, setPlaygroundRunning] = useState(false)
    const playgroundEndRef = useRef<HTMLDivElement>(null)

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
            for (const o of data.agent_overrides) {
                ov[o.agent_key] = o.llm_config_id
            }
            setOverrides(ov)
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
                .map(([agent_key, llm_config_id]) => ({ agent_key, llm_config_id }))
            const data = await setAgentLLMOverrides(list)
            const ov: Record<string, string> = {}
            for (const o of data) {
                ov[o.agent_key] = o.llm_config_id
            }
            setOverrides(ov)
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

    /** Извлечь только итоговый ответ ИИ (narrative). План и время выполнения — только в «Подробности (JSON)». */
    function formatPlaygroundResult(result: Record<string, unknown>): string {
        const status = result.status as string
        if (status === 'error') {
            return `Ошибка: ${result.error ?? 'Неизвестная ошибка'}`
        }
        const results = result.results as Record<string, { narrative?: { text?: string } | string }> | undefined
        if (results) {
            let narrativeText = (results.reporter?.narrative as { text?: string } | undefined)?.text
            if (!narrativeText && typeof results.reporter?.narrative === 'string') narrativeText = results.reporter.narrative
            if (!narrativeText) {
                for (const v of Object.values(results)) {
                    if (v && typeof v === 'object' && v.narrative) {
                        narrativeText = typeof v.narrative === 'string' ? v.narrative : (v.narrative as { text?: string }).text
                        if (narrativeText) break
                    }
                }
            }
            if (narrativeText?.trim()) return narrativeText.trim()
        }
        return 'Готово.'
    }

    const handleRunPlayground = async () => {
        const text = playgroundInput.trim()
        if (!text || playgroundRunning) return
        const userMsg: PlaygroundMessage = { id: `u-${Date.now()}`, role: 'user', content: text }
        // Локально считаем историю, включая текущее сообщение
        const historyForRequest: PlaygroundChatMessage[] = [
            ...playgroundMessages,
            userMsg,
        ].map((m) => ({
            role: m.role,
            content: m.content,
        })).slice(-10)

        setPlaygroundMessages((prev) => [...prev, userMsg])
        setPlaygroundInput('')
        setPlaygroundRunning(true)
        try {
            const result = await runPlayground(text, historyForRequest)
            const displayText = formatPlaygroundResult(result)
            const assistantMsg: PlaygroundMessage = {
                id: `a-${Date.now()}`,
                role: 'assistant',
                content: displayText,
                raw: result,
            }
            setPlaygroundMessages((prev) => [...prev, assistantMsg])
        } catch (e: unknown) {
            const errText = e instanceof Error ? e.message : 'Запуск не удался'
            setPlaygroundMessages((prev) => [
                ...prev,
                { id: `a-${Date.now()}`, role: 'assistant', content: `Ошибка: ${errText}` },
            ])
        } finally {
            setPlaygroundRunning(false)
        }
    }

    const handleClearPlayground = () => setPlaygroundMessages([])

    useEffect(() => {
        playgroundEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [playgroundMessages, playgroundRunning])

    return (
        <div className="space-y-6">
            {error && (
                <div className="rounded-md bg-destructive/10 text-destructive px-4 py-2 text-sm">
                    {error}
                </div>
            )}

            <Tabs defaultValue="settings">
                <TabsList>
                    <TabsTrigger value="settings">Настройки LLM</TabsTrigger>
                    <TabsTrigger value="playground">Playground (мультиагент)</TabsTrigger>
                </TabsList>

                <TabsContent value="settings" className="pt-4 space-y-6">
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
                                                <tr key={key} className="border-b">
                                                    <td className="p-2">{label}</td>
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
                </TabsContent>

                <TabsContent value="playground" className="pt-4 flex flex-col min-h-[420px]">
                    <div className="flex items-center justify-between pb-2 border-b border-border">
                        <p className="text-sm text-muted-foreground">
                            Чат с мультиагентным пайплайном. Используется модель по умолчанию и привязки агентов.
                        </p>
                        {playgroundMessages.length > 0 && (
                            <Button variant="ghost" size="icon" onClick={handleClearPlayground} title="Очистить историю" className="h-8 w-8">
                                <Trash2 className="w-4 h-4" />
                            </Button>
                        )}
                    </div>
                    <div className="flex-1 overflow-y-auto py-3 space-y-2 min-h-[200px]">
                        {playgroundMessages.length === 0 && !playgroundRunning ? (
                            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                                <Sparkles className="w-10 h-10 mb-3 text-primary/40" />
                                <p className="text-sm">Введите запрос и нажмите Отправить — мультиагент выполнит план и вернёт ответ.</p>
                            </div>
                        ) : (
                            playgroundMessages.map((msg) => (
                                <div
                                    key={msg.id}
                                    className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}
                                >
                                    <div
                                        className={cn(
                                            'max-w-[90%] rounded-lg px-3 py-2 text-sm',
                                            msg.role === 'user'
                                                ? 'bg-primary/15 text-foreground'
                                                : 'bg-muted text-foreground'
                                        )}
                                    >
                                        {msg.role === 'assistant' ? (
                                            <div className="prose prose-sm dark:prose-invert max-w-none break-words [&_pre]:text-xs [&_pre]:py-1.5 [&_pre]:px-2 [&_ul]:my-1 [&_ol]:my-1 [&_p]:my-0.5">
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                                            </div>
                                        ) : (
                                            <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                                        )}
                                        {msg.raw != null && (
                                            <details className="mt-2 pt-2 border-t border-border/30">
                                                <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                                                    Подробности (JSON)
                                                </summary>
                                                <pre className="mt-1 text-xs overflow-auto max-h-[200px] whitespace-pre-wrap break-words">
                                                    {JSON.stringify(msg.raw, null, 2)}
                                                </pre>
                                            </details>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                        {playgroundRunning && (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Мультиагент выполняется...
                            </div>
                        )}
                        <div ref={playgroundEndRef} />
                    </div>
                    <div className="pt-2 border-t border-border">
                        <div className="flex gap-2">
                            <Textarea
                                value={playgroundInput}
                                onChange={(e) => setPlaygroundInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault()
                                        handleRunPlayground()
                                    }
                                }}
                                placeholder="Например: проанализируй данные и предложи визуализацию..."
                                className="min-h-[48px] max-h-[120px] resize-none"
                                disabled={playgroundRunning}
                            />
                            <Button
                                onClick={handleRunPlayground}
                                disabled={!playgroundInput.trim() || playgroundRunning}
                                size="icon"
                                className="h-[48px] w-[48px] shrink-0"
                            >
                                {playgroundRunning ? (
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                ) : (
                                    <Send className="w-5 h-5" />
                                )}
                            </Button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1.5">
                            Enter — отправить, Shift+Enter — новая строка
                        </p>
                    </div>
                </TabsContent>
            </Tabs>
        </div>
    )
}
