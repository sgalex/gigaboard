/**
 * AI Assistant Store - manages AI chat state
 * См. docs/MULTI_AGENT_SYSTEM.md
 */
import { create } from 'zustand'
import { aiAssistantAPI } from '@/services/api'
import { notify } from './notificationStore'
import type { ChatMessage, AIChatRequest } from '@/types'
import { MessageRole } from '@/types'

interface SendAssistantMessageOptions {
    allowAutoFilter?: boolean
    requiredTables?: string[]
    filterExpression?: Record<string, any>
}
type AIAssistantScope = 'board' | 'dashboard'

interface AIAssistantStore {
    // State
    messages: ChatMessage[]
    sessionId: string | null
    isLoading: boolean
    error: string | null

    // Streaming state
    isStreaming: boolean
    currentStreamMessage: string

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
    handleStreamEnd: (fullResponse: string) => void
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

    setSocket: (socket: any) => set({ socket }),
    setSelectedNodes: (nodeIds: string[]) => set({ selectedNodeIds: nodeIds }),

    // Streaming handlers
    handleStreamStart: () => {
        set({ isStreaming: true, currentStreamMessage: '', error: null })
    },

    handleStreamChunk: (chunk: string) => {
        set((state) => ({
            currentStreamMessage: state.currentStreamMessage + chunk
        }))
    },

    handleStreamEnd: (fullResponse: string) => {
        const { sessionId } = get()

        // Создаем финальное сообщение ассистента
        const assistantMessage: ChatMessage = {
            id: `assistant-${Date.now()}`,
            board_id: '',
            user_id: '',
            session_id: sessionId || '',
            role: MessageRole.ASSISTANT,
            content: fullResponse,
            created_at: new Date().toISOString(),
        }

        set((state) => ({
            messages: [...state.messages, assistantMessage],
            isStreaming: false,
            currentStreamMessage: '',
        }))
    },

    handleStreamError: (error: string) => {
        set({
            error,
            isStreaming: false,
            currentStreamMessage: ''
        })
        notify.error(error, { title: 'AI Streaming Error' })
    },

    // Sidebar assistant should use the Multi-Agent REST endpoint.
    sendMessageStream: async (contextId: string, message: string, options?: SendAssistantMessageOptions, scope: AIAssistantScope = 'board') => {
        await get().sendMessage(contextId, message, options, scope)
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
