/**
 * AI Assistant Store - manages AI chat state
 * См. docs/MULTI_AGENT_SYSTEM.md
 */
import { create } from 'zustand'
import { aiAssistantAPI } from '@/services/api'
import { notify } from './notificationStore'
import type { ChatMessage, AIChatRequest } from '@/types'
import { MessageRole } from '@/types'

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

    sendMessage: (boardId: string, message: string) => Promise<void>
    sendMessageStream: (boardId: string, message: string) => void
    loadHistory: (boardId: string, sessionId?: string) => Promise<void>
    clearSession: (boardId: string) => Promise<void>

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

    // Send message with streaming (Socket.IO)
    sendMessageStream: (boardId: string, message: string) => {
        const { sessionId, selectedNodeIds, socket } = get()

        if (!socket) {
            console.error('❌ Socket not available')
            set({ error: 'Socket connection not available' })
            return
        }

        // Добавляем сообщение пользователя сразу
        const userMessage: ChatMessage = {
            id: `user-${Date.now()}`,
            board_id: boardId,
            user_id: '',
            session_id: sessionId || '',
            role: MessageRole.USER,
            content: message,
            created_at: new Date().toISOString(),
        }

        set((state) => ({
            messages: [...state.messages, userMessage]
        }))

        console.log('📤 Sending AI chat stream request:', {
            board_id: boardId,
            session_id: sessionId,
            message,
            socket_id: socket.id
        })

        // Отправляем через Socket.IO
        socket.emit('ai_chat_stream', {
            board_id: boardId,
            session_id: sessionId,
            message,
            selected_node_ids: selectedNodeIds.length > 0 ? selectedNodeIds : undefined,
        })
    },

    // Send message to AI (REST fallback)
    sendMessage: async (boardId: string, message: string) => {
        const { sessionId, selectedNodeIds } = get()

        set({ isLoading: true, error: null })

        try {
            const request: AIChatRequest = {
                message,
                session_id: sessionId || undefined,
                context: selectedNodeIds.length > 0 ? { selected_nodes: selectedNodeIds } : undefined,
            }

            const response = await aiAssistantAPI.chat(boardId, request)

            // Update session ID if new
            if (!sessionId) {
                set({ sessionId: response.data.session_id })
            }

            // Create user message
            const userMessage: ChatMessage = {
                id: `temp-user-${Date.now()}`,
                board_id: boardId,
                user_id: '',
                session_id: response.data.session_id,
                role: MessageRole.USER,
                content: message,
                created_at: new Date().toISOString(),
            }

            // Create assistant message
            const assistantMessage: ChatMessage = {
                id: `temp-assistant-${Date.now()}`,
                board_id: boardId,
                user_id: '',
                session_id: response.data.session_id,
                role: MessageRole.ASSISTANT,
                content: response.data.message,
                suggested_actions: response.data.suggested_actions,
                created_at: new Date().toISOString(),
            }

            // Add messages to state
            set((state) => ({
                messages: [...state.messages, userMessage, assistantMessage],
                isLoading: false,
            }))

        } catch (error: any) {
            const errorMessage = error.response?.data?.detail || 'Не удалось отправить сообщение'
            set({ error: errorMessage, isLoading: false })
            notify.error(errorMessage, { title: 'AI Assistant' })
        }
    },

    // Load chat history
    loadHistory: async (boardId: string, sessionId?: string) => {
        set({ isLoading: true, error: null })

        try {
            // Используем новый endpoint для получения истории пользователя
            const response = await aiAssistantAPI.getMyHistory(boardId, 50)

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
    clearSession: async (boardId: string) => {
        const { sessionId } = get()
        if (!sessionId) return

        try {
            await aiAssistantAPI.deleteSession(boardId, sessionId)
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
