/**
 * Hook for AI Assistant Socket.IO streaming
 */
import { useEffect } from 'react'
import { useAIAssistantStore } from '@/store/aiAssistantStore'

export function useAIStreaming(
    contextId: string | undefined,
    scope: 'board' | 'dashboard' = 'board',
) {
    const {
        socket,
        handleStreamStart,
        handleStreamChunk,
        handleStreamProgress,
        handleStreamEnd,
        handleStreamError,
        loadHistory,
    } = useAIAssistantStore()

    // Загрузка истории при монтировании
    useEffect(() => {
        if (!contextId) return

        console.log(`📚 Loading chat history for ${scope}:`, contextId)
        loadHistory(contextId, undefined, scope)
    }, [contextId, scope, loadHistory])

    useEffect(() => {
        if (!contextId || !socket) return

        console.log(`🤖 Setting up AI streaming handlers for ${scope}:`, contextId, 'socket:', socket.id)

        // Handler для начала streaming
        const onStreamStart = (data: { session_id: string; board_id: string }) => {
            console.log('🚀 AI Stream started:', data.session_id)

            // Сохраняем session_id в store (больше не используем localStorage)
            if (data.session_id && data.session_id !== 'null') {
                useAIAssistantStore.setState({ sessionId: data.session_id })
            }

            handleStreamStart()
        }

        // Handler для chunks
        const onStreamChunk = (data: { session_id: string; chunk: string }) => {
            handleStreamChunk(data.chunk)
        }

        // Handler для прогресса по шагам мультиагента
        const onStreamProgress = (data: {
            session_id: string
            event?: string
            agent_label?: string
            task?: string
            steps?: string[]
            step_index?: number
            total_steps?: number
            completed_count?: number
        }) => {
            handleStreamProgress(data)
        }

        // Handler для завершения
        const onStreamEnd = (data: { session_id: string; full_response: string; suggested_actions?: any[] }) => {
            console.log('✅ AI Stream completed:', data.session_id)
            handleStreamEnd({
                fullResponse: data.full_response,
                suggestedActions: data.suggested_actions,
            })
        }

        // Handler для ошибок
        const onStreamError = (data: { error: string; session_id?: string }) => {
            console.error('❌ AI Stream error:', data.error)
            handleStreamError(data.error)
        }

        // Подписываемся на события
        socket.on('ai:stream:start', onStreamStart)
        socket.on('ai:stream:chunk', onStreamChunk)
        socket.on('ai:stream:progress', onStreamProgress)
        socket.on('ai:stream:end', onStreamEnd)
        socket.on('ai:stream:error', onStreamError)

        // Cleanup
        return () => {
            socket.off('ai:stream:start', onStreamStart)
            socket.off('ai:stream:chunk', onStreamChunk)
            socket.off('ai:stream:progress', onStreamProgress)
            socket.off('ai:stream:end', onStreamEnd)
            socket.off('ai:stream:error', onStreamError)
        }
    }, [contextId, scope, socket, handleStreamStart, handleStreamChunk, handleStreamProgress, handleStreamEnd, handleStreamError])
}
