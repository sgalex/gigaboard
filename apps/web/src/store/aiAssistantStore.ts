/**
 * AI Assistant Store - manages AI chat state
 * См. docs/MULTI_AGENT_SYSTEM.md
 */
import { create } from 'zustand'
import { aiAssistantAPI } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { notify } from './notificationStore'
import type { ChatMessage, AIChatRequest } from '@/types'
import { MessageRole } from '@/types'
import {
    mergePlanSteps,
    applyProgressToSteps,
    metaFromSteps,
} from '@/lib/multiAgentProgress'

interface SendAssistantMessageOptions {
    allowAutoFilter?: boolean
    requiredTables?: string[]
    filterExpression?: Record<string, any>
}
type AIAssistantScope = 'board' | 'dashboard'

type ProgressStepStatus = 'pending' | 'running' | 'completed' | 'failed'

type AssistantProgressStep = {
    id: string
    text: string
    status: ProgressStepStatus
}

type AssistantProgressMeta = {
    current: number
    total: number | null
}

type AssistantProgressEvent = {
    event?: string
    task?: string
    steps?: string[]
    step_index?: number
    total_steps?: number
    completed_count?: number
}

interface AIAssistantStore {
    // State
    messages: ChatMessage[]
    sessionId: string | null
    isLoading: boolean
    error: string | null

    // Streaming state
    isStreaming: boolean
    currentStreamMessage: string
    progressSteps: AssistantProgressStep[]
    progressMeta: AssistantProgressMeta

    // Socket reference (set by BoardPage)
    socket: any

    // UI State
    selectedNodeIds: string[]

    // Actions
    setSocket: (socket: any) => void
    setSelectedNodes: (nodeIds: string[]) => void

    sendMessage: (contextId: string, message: string, options?: SendAssistantMessageOptions, scope?: AIAssistantScope) => Promise<void>
    sendMessageStream: (contextId: string, message: string, options?: SendAssistantMessageOptions, scope?: AIAssistantScope) => Promise<void>
    loadHistory: (contextId: string, sessionId?: string, scope?: AIAssistantScope) => Promise<void>
    clearSession: (contextId: string, scope?: AIAssistantScope) => Promise<void>

    // Streaming handlers
    handleStreamStart: () => void
    handleStreamChunk: (chunk: string) => void
    handleStreamProgress: (payload: AssistantProgressEvent) => void
    handleStreamEnd: (payload: { fullResponse: string; suggestedActions?: any[] }) => void
    handleStreamError: (error: string) => void

    // Internal
    addMessage: (message: ChatMessage) => void
    setLoading: (loading: boolean) => void
    setError: (error: string | null) => void
}

export const useAIAssistantStore = create<AIAssistantStore>((set, get) => ({
    // Initial State
    messages: [],
    sessionId: null,
    isLoading: false,
    error: null,
    selectedNodeIds: [],
    socket: null,

    // Streaming state
    isStreaming: false,
    currentStreamMessage: '',
    progressSteps: [],
    progressMeta: { current: 0, total: null },

    setSocket: (socket: any) => set({ socket }),
    setSelectedNodes: (nodeIds: string[]) => set({ selectedNodeIds: nodeIds }),

    // Streaming handlers
    handleStreamStart: () => {
        set({
            isStreaming: true,
            isLoading: false,
            currentStreamMessage: '',
            error: null,
            progressSteps: [],
            progressMeta: { current: 0, total: null },
        })
    },

    handleStreamChunk: (chunk: string) => {
        set((state) => ({
            currentStreamMessage: state.currentStreamMessage + chunk
        }))
    },

    handleStreamProgress: (payload: AssistantProgressEvent) => {
        if (payload?.event === 'plan_update' && Array.isArray(payload.steps) && payload.steps.length > 0) {
            set((state) => {
                const incomingSteps = (payload.steps ?? [])
                    .map((s) => String(s || '').trim())
                    .filter((s) => s.length > 0)
                if (incomingSteps.length === 0) return {}

                const nextSteps = mergePlanSteps(
                    state.progressSteps,
                    incomingSteps,
                    payload.completed_count,
                    'assistant'
                )
                return {
                    progressSteps: nextSteps,
                    progressMeta: metaFromSteps(nextSteps),
                }
            })
            return
        }

        set((state) => {
            const stepIndexRaw = payload?.step_index
            const totalStepsRaw = payload?.total_steps
            const stepIndex =
                typeof stepIndexRaw === 'number' && stepIndexRaw > 0 ? Math.floor(stepIndexRaw) : null
            const totalSteps =
                typeof totalStepsRaw === 'number' && totalStepsRaw > 0 ? Math.floor(totalStepsRaw) : null
            const taskText = String(payload?.task || '').trim()

            let nextSteps = applyProgressToSteps(
                state.progressSteps,
                taskText,
                stepIndex ?? undefined,
                'assistant'
            )

            const prevMeta = state.progressMeta
            const nextTotal = totalSteps != null ? Math.max(prevMeta.total ?? 0, totalSteps) : prevMeta.total
            const meta = metaFromSteps(nextSteps)
            return {
                progressSteps: nextSteps,
                progressMeta: {
                    current: meta.current,
                    total: nextTotal ?? meta.total,
                },
            }
        })
    },

    handleStreamEnd: ({ fullResponse, suggestedActions }) => {
        const { sessionId } = get()

        // Создаем финальное сообщение ассистента
        const assistantMessage: ChatMessage = {
            id: `assistant-${Date.now()}`,
            board_id: '',
            user_id: '',
            session_id: sessionId || '',
            role: MessageRole.ASSISTANT,
            content: fullResponse,
            suggested_actions: suggestedActions,
            created_at: new Date().toISOString(),
        }

        set((state) => ({
            messages: [...state.messages, assistantMessage],
            isStreaming: false,
            isLoading: false,
            currentStreamMessage: '',
            progressSteps: [],
            progressMeta: { current: 0, total: null },
        }))
    },

    handleStreamError: (error: string) => {
        set((state) => {
            const nextSteps =
                state.progressSteps.length > 0
                    ? state.progressSteps.map((step, idx) =>
                          idx === state.progressSteps.length - 1 && step.status === 'running'
                              ? { ...step, status: 'failed' as const }
                              : step
                      )
                    : []
            return {
                error,
                isStreaming: false,
                isLoading: false,
                currentStreamMessage: '',
                progressSteps: nextSteps,
                progressMeta: {
                    current: state.progressMeta.current,
                    total: state.progressMeta.total,
                },
            }
        })
        notify.error(error, { title: 'AI Streaming Error' })
    },

    // Multi-Agent ответ через Socket.IO (прогресс ai:stream:progress). REST — только если нет сокета.
    sendMessageStream: async (contextId: string, message: string, options?: SendAssistantMessageOptions, scope: AIAssistantScope = 'board') => {
        const { socket, sessionId, selectedNodeIds } = get()
        if (!socket) {
            await get().sendMessage(contextId, message, options, scope)
            return
        }
        if (scope === 'dashboard' && !useAuthStore.getState().token) {
            await get().sendMessage(contextId, message, options, scope)
            return
        }

        if (!socket.connected && typeof socket.connect === 'function') {
            try {
                socket.connect()
            } catch {
                // If reconnect throws, emit below still may be queued by socket.io client.
            }
        }

        const optimisticUserMessage: ChatMessage = {
            id: `user-${Date.now()}`,
            board_id: contextId,
            user_id: '',
            session_id: sessionId || '',
            role: MessageRole.USER,
            content: message,
            created_at: new Date().toISOString(),
        }

        set((state) => ({
            messages: [...state.messages, optimisticUserMessage],
            isLoading: true,
            error: null,
            currentStreamMessage: '',
        }))

        const token = useAuthStore.getState().token
        socket.emit('ai_chat_stream', {
            board_id: contextId,
            session_id: sessionId || undefined,
            message,
            selected_node_ids: selectedNodeIds,
            allow_auto_filter: Boolean(options?.allowAutoFilter),
            required_tables: options?.requiredTables || [],
            filter_expression: options?.filterExpression,
            scope,
            access_token: scope === 'dashboard' ? token ?? undefined : undefined,
        })
    },

    // Send message to AI (REST fallback)
    sendMessage: async (
        contextId: string,
        message: string,
        options?: SendAssistantMessageOptions,
        scope: AIAssistantScope = 'board',
    ) => {
        const { sessionId, selectedNodeIds } = get()
        const optimisticUserMessageId = `user-${Date.now()}`

        set({ isLoading: true, error: null })

        // Optimistic update: message should appear immediately in chat.
        const optimisticUserMessage: ChatMessage = {
            id: optimisticUserMessageId,
            board_id: contextId,
            user_id: '',
            session_id: sessionId || '',
            role: MessageRole.USER,
            content: message,
            created_at: new Date().toISOString(),
        }
        set((state) => ({
            messages: [...state.messages, optimisticUserMessage],
        }))

        try {
            const request: AIChatRequest = {
                message,
                session_id: sessionId || undefined,
                context: {
                    mode: scope,
                    selected_node_ids: selectedNodeIds,
                    allow_auto_filter: Boolean(options?.allowAutoFilter),
                    required_tables: options?.requiredTables,
                    filter_expression: options?.filterExpression,
                },
            }

            const response = scope === 'dashboard'
                ? await aiAssistantAPI.chatDashboard(contextId, request)
                : await aiAssistantAPI.chat(contextId, request)
            const responseSessionId = response.data.session_id

            // Update session ID if new
            if (!sessionId) set({ sessionId: responseSessionId })

            // Create assistant message
            const assistantMessage: ChatMessage = {
                id: `temp-assistant-${Date.now()}`,
                board_id: contextId,
                user_id: '',
                session_id: responseSessionId,
                role: MessageRole.ASSISTANT,
                content: response.data.response,
                context: response.data.context_used || undefined,
                suggested_actions: response.data.suggested_actions,
                created_at: new Date().toISOString(),
            }

            // Append assistant and reconcile optimistic user message session.
            set((state) => ({
                messages: [
                    ...state.messages.map((msg) =>
                        msg.id === optimisticUserMessageId
                            ? { ...msg, session_id: responseSessionId }
                            : msg
                    ),
                    assistantMessage,
                ],
                isLoading: false,
            }))

        } catch (error: any) {
            const errorMessage = error.response?.data?.detail || 'Не удалось отправить сообщение'
            set({ error: errorMessage, isLoading: false })
            notify.error(errorMessage, { title: 'AI Assistant' })
        }
    },

    // Load chat history
    loadHistory: async (contextId: string, sessionId?: string, scope: AIAssistantScope = 'board') => {
        set({ isLoading: true, error: null })

        try {
            // Используем новый endpoint для получения истории пользователя
            const response = scope === 'dashboard'
                ? await aiAssistantAPI.getMyHistoryDashboard(contextId, 50)
                : await aiAssistantAPI.getMyHistory(contextId, 50)

            set({
                messages: response.data.messages,
                sessionId: response.data.session_id || null,
                isLoading: false,
            })
        } catch (error: any) {
            // Если 404 или нет данных - просто нет истории, не показываем ошибку
            if (error.response?.status === 404 || error.response?.status === 500) {
                set({ messages: [], sessionId: null, isLoading: false })
            } else {
                const errorMessage = error.response?.data?.detail || 'Не удалось загрузить историю'
                set({ error: errorMessage, isLoading: false })
                console.error('Failed to load chat history:', error)
            }
        }
    },

    // Clear chat session
    clearSession: async (contextId: string, scope: AIAssistantScope = 'board') => {
        const { sessionId } = get()
        if (!sessionId) return

        try {
            if (scope === 'dashboard') {
                await aiAssistantAPI.deleteSessionDashboard(contextId, sessionId)
            } else {
                await aiAssistantAPI.deleteSession(contextId, sessionId)
            }
            set({
                messages: [],
                sessionId: null,
            })
            notify.success('История чата очищена', { title: 'AI Assistant' })
        } catch (error: any) {
            const errorMessage = error.response?.data?.detail || 'Не удалось очистить историю'
            notify.error(errorMessage, { title: 'AI Assistant' })
        }
    },

    // Internal Actions
    addMessage: (message: ChatMessage) =>
        set((state) => ({ messages: [...state.messages, message] })),
    setLoading: (loading: boolean) => set({ isLoading: loading }),
    setError: (error: string | null) => set({ error }),
}))
