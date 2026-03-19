/**
 * Хук с общей логикой для всех диалогов источников.
 * 
 * Содержит:
 * - Доступ к boardId и user
 * - createSourceNode
 * - Состояние загрузки
 * - Закрытие диалога
 */
import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useBoardStore } from '@/store/boardStore'
import { useAuthStore } from '@/store/authStore'
import { useFilterStore } from '@/store/filterStore'
import { useLibraryStore } from '@/store/libraryStore'
import { notify } from '@/store/notificationStore'
import { SourceType } from '@/types'
import { SourceConfig, CreateSourceResult } from './types'

interface UseSourceDialogOptions {
    sourceType: SourceType
    onClose: () => void
    position?: { x: number; y: number }
}

export function useSourceDialog({ sourceType, onClose, position = { x: 100, y: 100 } }: UseSourceDialogOptions) {
    const { boardId } = useParams<{ boardId: string }>()
    const { user } = useAuthStore()
    const { createSourceNode, updateSourceNode } = useBoardStore()

    const [isLoading, setIsLoading] = useState(false)

    const create = useCallback(async (
        config: SourceConfig,
        metadata?: Record<string, any>,
        data?: { text?: string; tables?: Array<{ name?: string; columns?: Array<{ name: string; type?: string }>; rows?: Record<string, unknown>[]; row_count?: number; column_count?: number }> }
    ): Promise<CreateSourceResult> => {
        if (!boardId) {
            notify.error('Board ID не найден')
            return { success: false, error: 'Board ID не найден' }
        }

        if (!user) {
            notify.error('Пользователь не авторизован')
            return { success: false, error: 'Пользователь не авторизован' }
        }

        setIsLoading(true)

        try {
            const payload: Parameters<typeof createSourceNode>[1] = {
                board_id: boardId,
                source_type: sourceType,
                config,
                metadata: metadata || {},
                position,
                created_by: user.id,
            }
            if (data != null) payload.data = data
            const result = await createSourceNode(boardId, payload)

            if (result) {
                onClose()

                // Re-fetch dimensions and node tables — auto-detection runs server-side after node creation
                const projectId = useBoardStore.getState().currentBoard?.project_id
                if (projectId) {
                    useFilterStore.getState().loadDimensions(projectId)
                    const boards = useBoardStore.getState().boards.filter(b => b.project_id === projectId)
                    if (boards.length > 0) {
                        useLibraryStore.getState().fetchNodeTables(boards)
                    }
                }

                return { success: true, sourceId: result.id }
            } else {
                return { success: false, error: 'Не удалось создать источник' }
            }
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось создать источник данных'
            notify.error(message)
            return { success: false, error: message }
        } finally {
            setIsLoading(false)
        }
    }, [boardId, user, sourceType, position, createSourceNode, onClose])

    const update = useCallback(async (
        sourceId: string,
        config: SourceConfig,
        metadata?: Record<string, any>
    ): Promise<CreateSourceResult> => {
        setIsLoading(true)

        try {
            await updateSourceNode(sourceId, {
                config,
                metadata,
            })

            notify.success('Настройки источника обновлены')
            onClose()

            // Re-fetch dimensions and node tables — auto-detection re-runs server-side after node update
            const projectId = useBoardStore.getState().currentBoard?.project_id
            if (projectId) {
                useFilterStore.getState().loadDimensions(projectId)
                const boards = useBoardStore.getState().boards.filter(b => b.project_id === projectId)
                if (boards.length > 0) {
                    useLibraryStore.getState().fetchNodeTables(boards)
                }
            }

            return { success: true }
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось обновить источник'
            notify.error(message)
            return { success: false, error: message }
        } finally {
            setIsLoading(false)
        }
    }, [updateSourceNode, onClose])

    return {
        boardId,
        user,
        isLoading,
        create,
        update,
    }
}
