/**
 * Клиентское логирование результата чата извлечения из документа (мультиагент).
 * Серверный JSONL-трейс: apps/backend/logs/multi_agent_traces/orchestrator_trace_YYYYMMDD.jsonl
 *
 * Включение в браузере: localStorage.setItem('gigaboard_ma_trace', '1')
 * В dev-сборке лог пишется всегда (import.meta.env.DEV).
 */
export type DocumentExtractionTracePayload = {
    fileId?: string
    sessionId?: string | null
    traceFilePath?: string | null
    executionTimeMs?: number | null
    tableCount?: number
    narrativePreview?: string
}

export function logDocumentExtractionMultiAgentTrace(payload: DocumentExtractionTracePayload): void {
    const enabled =
        import.meta.env.DEV ||
        (typeof localStorage !== 'undefined' && localStorage.getItem('gigaboard_ma_trace') === '1')
    if (!enabled) return
    console.info('[GigaBoard][DocumentSource][multi-agent]', payload)
}
