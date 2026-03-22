import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import {
    fetchUserAISettings,
    updateUserAISettings,
    type UserAISettings,
} from '@/services/userSettingsApi'

const KNOWN_KEYS: {
    key: string
    label: string
    kind: 'bool' | 'int' | 'str'
    placeholder?: string
}[] = [
    { key: 'MULTI_AGENT_TRACE_ENABLED', label: 'Запись трейсов оркестратора (JSONL)', kind: 'bool' },
    {
        key: 'MULTI_AGENT_TRACE_DIR',
        label: 'Каталог для трейсов (пусто — дефолт в logs/)',
        kind: 'str',
        placeholder: 'например C:\\logs\\ma или /var/log/gigaboard/ma',
    },
    {
        key: 'MULTI_AGENT_MAX_VALIDATION_RECOVERY',
        label: 'Макс. replan после ошибки валидации',
        kind: 'int',
    },
    {
        key: 'MULTI_AGENT_TOOL_MAX_ROUNDS_PER_STEP',
        label:
            'Макс. раундов tool loop на шаг агента (readTableList/readTableData; значения ниже 15 поднимаются до 15)',
        kind: 'int',
    },
    {
        key: 'MULTI_AGENT_CONTEXT_WARN_CHARS',
        label: 'Порог предупреждения о размере контекста (символов)',
        kind: 'int',
    },
    { key: 'MULTI_AGENT_CONTEXT_MAX_SOURCES_PER_RESULT', label: 'Макс. источников на результат', kind: 'int' },
    {
        key: 'MULTI_AGENT_CONTEXT_MAX_SOURCE_CONTENT_CHARS',
        label: 'Макс. символов контента на источник',
        kind: 'int',
    },
    { key: 'MULTI_AGENT_CONTEXT_MAX_TABLES_PER_RESULT', label: 'Макс. таблиц на результат', kind: 'int' },
    { key: 'MULTI_AGENT_CONTEXT_MAX_TABLE_ROWS', label: 'Макс. строк таблицы в контексте', kind: 'int' },
    { key: 'MULTI_AGENT_CONTEXT_MAX_FINDINGS_PER_RESULT', label: 'Макс. findings на результат', kind: 'int' },
    { key: 'MULTI_AGENT_CONTEXT_MAX_CODE_BLOCKS_PER_RESULT', label: 'Макс. code blocks на результат', kind: 'int' },
    { key: 'MULTI_AGENT_CONTEXT_MAX_CHAT_MESSAGES', label: 'Макс. сообщений чата в контексте', kind: 'int' },
    {
        key: 'MULTI_AGENT_CONTEXT_MAX_CHAT_MESSAGE_CHARS',
        label: 'Макс. символов на сообщение чата',
        kind: 'int',
    },
    { key: 'MULTI_AGENT_CONTEXT_MAX_INPUT_PREVIEW_TABLES', label: 'Превью input: макс. таблиц', kind: 'int' },
    { key: 'MULTI_AGENT_CONTEXT_MAX_INPUT_PREVIEW_COLUMNS', label: 'Превью input: макс. колонок', kind: 'int' },
    { key: 'MULTI_AGENT_CONTEXT_MAX_CATALOG_PREVIEW_TABLES', label: 'Превью каталога: макс. таблиц', kind: 'int' },
    { key: 'MULTI_AGENT_CONTEXT_MAX_CATALOG_PREVIEW_COLUMNS', label: 'Превью каталога: макс. колонок', kind: 'int' },
]

function getBool(ma: Record<string, unknown>, key: string, fallback: boolean): boolean {
    const v = ma[key]
    if (v === undefined || v === null) return fallback
    if (typeof v === 'boolean') return v
    const s = String(v).toLowerCase()
    return s === '1' || s === 'true' || s === 'yes' || s === 'on'
}

function getStr(ma: Record<string, unknown>, key: string): string {
    const v = ma[key]
    if (v === undefined || v === null) return ''
    return String(v)
}

function getIntStr(ma: Record<string, unknown>, key: string): string {
    const v = ma[key]
    if (v === undefined || v === null) return ''
    return String(v)
}

export function MultiAgentUserSettingsPanel() {
    const [base, setBase] = useState<UserAISettings | null>(null)
    const [ma, setMa] = useState<Record<string, unknown>>({})
    const [advancedJson, setAdvancedJson] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [savedOk, setSavedOk] = useState(false)

    const load = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const s = await fetchUserAISettings()
            setBase(s)
            const raw = s.multi_agent_settings
            const obj =
                raw && typeof raw === 'object' && !Array.isArray(raw)
                    ? (raw as Record<string, unknown>)
                    : {}
            setMa(obj)
            const known = new Set(KNOWN_KEYS.map((k) => k.key))
            const extra: Record<string, unknown> = {}
            for (const [k, v] of Object.entries(obj)) {
                if (!known.has(k)) extra[k] = v
            }
            setAdvancedJson(
                Object.keys(extra).length ? JSON.stringify(extra, null, 2) : ''
            )
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Не удалось загрузить настройки')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void load()
    }, [load])

    const patchMa = (key: string, value: unknown) => {
        setMa((prev) => {
            const next = { ...prev }
            if (value === '' || value === undefined) {
                delete next[key]
            } else {
                next[key] = value
            }
            return next
        })
        setSavedOk(false)
    }

    const handleSave = async () => {
        if (!base) return
        let extra: Record<string, unknown> = {}
        if (advancedJson.trim()) {
            try {
                const parsed = JSON.parse(advancedJson) as unknown
                if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
                    setError('Доп. JSON должен быть объектом { "KEY": value }')
                    return
                }
                extra = parsed as Record<string, unknown>
            } catch {
                setError('Некорректный JSON в поле «Дополнительные ключи»')
                return
            }
        }
        const merged: Record<string, unknown> = { ...ma }
        for (const [k, v] of Object.entries(extra)) {
            merged[k] = v
        }
        setSaving(true)
        setError(null)
        setSavedOk(false)
        try {
            await updateUserAISettings({
                provider: base.provider,
                gigachat_model: base.gigachat_model,
                gigachat_scope: base.gigachat_scope,
                external_base_url: base.external_base_url,
                external_default_model: base.external_default_model,
                external_timeout_seconds: base.external_timeout_seconds,
                temperature: base.temperature,
                max_tokens: base.max_tokens,
                preferred_style: base.preferred_style,
                multi_agent_settings: merged,
            })
            setSavedOk(true)
            await load()
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Ошибка сохранения')
        } finally {
            setSaving(false)
        }
    }

    if (loading) {
        return <p className="text-sm text-muted-foreground">Загрузка…</p>
    }

    return (
        <div className="space-y-6">
            <div className="space-y-1">
                <h2 className="text-lg font-semibold">Multi-Agent</h2>
                <p className="text-sm text-muted-foreground">
                    Параметры пайплайна (те же имена, что переменные окружения{' '}
                    <code className="text-xs">MULTI_AGENT_*</code>). Пустое поле — использовать значение
                    сервера (env или дефолт кода).
                </p>
            </div>

            {error && (
                <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {error}
                </div>
            )}
            {savedOk && (
                <p className="text-sm text-green-600 dark:text-green-400">Сохранено.</p>
            )}

            <div className="grid gap-6 sm:grid-cols-2">
                {KNOWN_KEYS.map(({ key, label, kind, placeholder }) => (
                    <div key={key} className="space-y-2 sm:col-span-2">
                        {kind === 'bool' ? (
                            <div className="flex items-center justify-between gap-4 rounded-lg border border-border p-3">
                                <Label htmlFor={key} className="text-sm font-normal leading-snug">
                                    {label}
                                </Label>
                                <Switch
                                    id={key}
                                    checked={getBool(ma, key, true)}
                                    onCheckedChange={(c) => patchMa(key, c)}
                                />
                            </div>
                        ) : kind === 'int' ? (
                            <>
                                <Label htmlFor={key}>{label}</Label>
                                <Input
                                    id={key}
                                    type="number"
                                    inputMode="numeric"
                                    placeholder="по умолчанию сервера"
                                    value={getIntStr(ma, key)}
                                    onChange={(e) => {
                                        const v = e.target.value
                                        if (v === '') patchMa(key, '')
                                        else {
                                            const n = parseInt(v, 10)
                                            if (!Number.isNaN(n)) patchMa(key, n)
                                        }
                                    }}
                                />
                            </>
                        ) : (
                            <>
                                <Label htmlFor={key}>{label}</Label>
                                <Input
                                    id={key}
                                    placeholder={placeholder}
                                    value={getStr(ma, key)}
                                    onChange={(e) => patchMa(key, e.target.value.trim() || '')}
                                />
                            </>
                        )}
                    </div>
                ))}
            </div>

            <div className="space-y-2">
                <Label htmlFor="ma-advanced">Дополнительные ключи (JSON)</Label>
                <p className="text-xs text-muted-foreground">
                    Например таймауты:{' '}
                    <code className="text-[11px]">
                        {`{"MULTI_AGENT_TIMEOUT_PLANNER_DEFAULT":"45"}`}
                    </code>
                </p>
                <Textarea
                    id="ma-advanced"
                    rows={6}
                    className="font-mono text-xs"
                    placeholder="{}"
                    value={advancedJson}
                    onChange={(e) => {
                        setAdvancedJson(e.target.value)
                        setSavedOk(false)
                    }}
                />
            </div>

            <Button type="button" onClick={() => void handleSave()} disabled={saving || !base}>
                {saving ? 'Сохранение…' : 'Сохранить'}
            </Button>
        </div>
    )
}
