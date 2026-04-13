/**
 * Board Store - manages boards and nodes state
 */
import { create } from 'zustand'
import {
    boardsAPI,
    widgetNodesAPI,
    commentNodesAPI,
    edgesAPI,
    sourceNodesAPI,
    contentNodesAPI
} from '@/services/api'
import { notify } from './notificationStore'
import { useLibraryStore } from './libraryStore'
import type {
    Board,
    BoardWithNodes,
    BoardCreate,
    BoardUpdate,
    WidgetNode,
    WidgetNodeCreate,
    WidgetNodeUpdate,
    CommentNode,
    CommentNodeCreate,
    CommentNodeUpdate,
    SourceNode,
    SourceNodeCreate,
    SourceNodeUpdate,
    ContentNode,
    ContentNodeCreate,
    ContentNodeUpdate,
    Edge,
    EdgeCreate,
    EdgeUpdate,
} from '@/types'
import { EdgeType } from '@/types'

/** Тип source для EdgeCreate — как в backend (snake_case). */
function resolveSourceNodeTypeForEdge(
    sourceId: string,
    sourceNodes: SourceNode[],
    contentNodes: ContentNode[]
): string {
    if (sourceNodes.some((s) => s.id === sourceId)) return 'source_node'
    if (contentNodes.some((c) => c.id === sourceId)) return 'content_node'
    return 'content_node'
}

/**
 * Входящие TRANSFORMATION к исходному узлу (те же источники, что на графе).
 * Если рёбер нет — fallback по lineage.source_node_ids / source_node_id.
 */
function getTransformationSourcesForDuplicate(
    node: ContentNode,
    edges: Edge[],
    sourceNodes: SourceNode[],
    contentNodes: ContentNode[]
): Array<{ sourceId: string; sourceType: string; template?: Edge }> {
    const incoming = edges.filter(
        (e) =>
            e.target_node_id === node.id &&
            String(e.edge_type) === String(EdgeType.TRANSFORMATION)
    )
    if (incoming.length > 0) {
        return incoming.map((e) => ({
            sourceId: e.source_node_id,
            sourceType: e.source_node_type,
            template: e,
        }))
    }
    const lineage = node.lineage as Record<string, unknown> | undefined
    if (!lineage) return []
    const idSet = new Set<string>()
    const multi = lineage.source_node_ids
    if (Array.isArray(multi)) {
        for (const x of multi) {
            if (typeof x === 'string') idSet.add(x)
        }
    }
    const single = lineage.source_node_id
    if (typeof single === 'string' && single) idSet.add(single)
    const parents = lineage.parent_content_ids
    if (Array.isArray(parents)) {
        for (const x of parents) {
            if (typeof x === 'string') idSet.add(x)
        }
    }
    return Array.from(idSet).map((id) => ({
        sourceId: id,
        sourceType: resolveSourceNodeTypeForEdge(id, sourceNodes, contentNodes),
    }))
}

interface BoardStore {
    // State
    boards: BoardWithNodes[]
    currentBoard: Board | null
    widgetNodes: WidgetNode[]
    commentNodes: CommentNode[]
    sourceNodes: SourceNode[]
    contentNodes: ContentNode[]
    edges: Edge[]
    isLoading: boolean
    error: string | null

    // Board Actions
    fetchBoards: (projectId?: string) => Promise<void>
    createBoard: (data: BoardCreate) => Promise<Board | null>
    fetchBoard: (id: string) => Promise<void>
    updateBoard: (id: string, data: BoardUpdate, silent?: boolean) => Promise<void>
    deleteBoard: (id: string) => Promise<void>
    setCurrentBoard: (board: Board | null) => void

    // WidgetNode Actions
    fetchWidgetNodes: (boardId: string) => Promise<void>
    createWidgetNode: (boardId: string, data: WidgetNodeCreate) => Promise<WidgetNode | null>
    /** Копия виджета и новой связи VISUALIZATION к тому же ContentNode/SourceNode. */
    duplicateWidgetNode: (widget: WidgetNode) => Promise<WidgetNode | null>
    updateWidgetNode: (boardId: string, widgetNodeId: string, data: WidgetNodeUpdate) => Promise<void>
    deleteWidgetNode: (boardId: string, widgetNodeId: string, projectId?: string) => Promise<void>

    // CommentNode Actions
    fetchCommentNodes: (boardId: string) => Promise<void>
    createCommentNode: (boardId: string, data: CommentNodeCreate) => Promise<CommentNode | null>
    updateCommentNode: (boardId: string, commentNodeId: string, data: CommentNodeUpdate) => Promise<void>
    deleteCommentNode: (boardId: string, commentNodeId: string) => Promise<void>
    resolveCommentNode: (boardId: string, commentNodeId: string, isResolved: boolean) => Promise<void>

    // SourceNode Actions
    fetchSourceNodes: (boardId: string) => Promise<void>
    createSourceNode: (boardId: string, data: SourceNodeCreate) => Promise<SourceNode | null>
    updateSourceNode: (sourceNodeId: string, data: SourceNodeUpdate) => Promise<void>
    deleteSourceNode: (sourceNodeId: string) => Promise<void>
    validateSourceNode: (sourceNodeId: string) => Promise<boolean>
    extractFromSource: (sourceNodeId: string, params?: Record<string, any>) => Promise<ContentNode | null>
    refreshSourceNode: (sourceNodeId: string) => Promise<void>

    // ContentNode Actions
    fetchContentNodes: (boardId: string) => Promise<void>
    createContentNode: (boardId: string, data: ContentNodeCreate) => Promise<ContentNode | null>
    /** Независимая копия ContentNode (те же данные и lineage, новое имя и позиция). */
    duplicateContentNode: (node: ContentNode) => Promise<ContentNode | null>
    updateContentNode: (contentNodeId: string, data: ContentNodeUpdate) => Promise<void>
    deleteContentNode: (contentNodeId: string) => Promise<void>
    getContentTable: (contentNodeId: string, tableIndex: number) => Promise<any>
    getContentLineage: (contentNodeId: string) => Promise<any>
    getDownstreamContents: (contentNodeId: string) => Promise<ContentNode[]>
    transformContent: (contentNodeId: string, prompt: string, code?: string, transformationId?: string, targetNodeId?: string, chatHistory?: Array<{ role: string; content: string }>) => Promise<ContentNode | null>
    transformContents: (sourceContentIds: string[], code: string, description?: string, position?: { x: number, y: number }) => Promise<ContentNode | null>
    visualizeContent: (contentNodeId: string, params: {
        user_prompt?: string
        auto_refresh?: boolean
    }) => Promise<void>

    // Edge Actions
    fetchEdges: (boardId: string) => Promise<void>
    createEdge: (boardId: string, data: EdgeCreate) => Promise<Edge | null>
    updateEdge: (boardId: string, edgeId: string, data: EdgeUpdate) => Promise<void>
    deleteEdge: (boardId: string, edgeId: string) => Promise<void>

    // Utility
    clearError: () => void
    clearBoardData: () => void  // Clear all nodes and edges
}

export const useBoardStore = create<BoardStore>((set, get) => ({
    // Initial state
    boards: [],
    currentBoard: null,
    widgetNodes: [],
    commentNodes: [],
    sourceNodes: [],
    contentNodes: [],
    edges: [],
    isLoading: false,
    error: null,

    // Fetch all boards
    fetchBoards: async (projectId?: string) => {
        set({ isLoading: true, error: null })
        try {
            const response = await boardsAPI.list(projectId)
            set({ boards: response.data, isLoading: false })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось загрузить доски'
            set({ error: message, isLoading: false })
            notify.error(message, { title: 'Ошибка загрузки' })
        }
    },

    // Create new board
    createBoard: async (data: BoardCreate) => {
        set({ isLoading: true, error: null })
        try {
            const response = await boardsAPI.create(data)
            const newBoard = response.data

            set((state) => ({
                boards: [
                    {
                        ...newBoard,
                        widget_nodes_count: 0,
                        comment_nodes_count: 0,
                    },
                    ...state.boards,
                ],
                isLoading: false,
            }))

            notify.success(`Доска "${newBoard.name}" создана`, { title: 'Успех' })
            return newBoard
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось создать доску'
            set({ error: message, isLoading: false })
            notify.error(message, { title: 'Ошибка создания' })
            return null
        }
    },

    // Fetch single board
    fetchBoard: async (id: string) => {
        set({ isLoading: true, error: null })
        try {
            const response = await boardsAPI.get(id)
            set({ currentBoard: response.data, isLoading: false })

            // Fetch all nodes and edges for this board
            await Promise.all([
                get().fetchWidgetNodes(id),
                get().fetchCommentNodes(id),
                get().fetchSourceNodes(id),
                get().fetchContentNodes(id),
                get().fetchEdges(id),
            ])
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось загрузить доску'
            set({ error: message, isLoading: false, currentBoard: null })
            notify.error(message, { title: 'Ошибка загрузки' })
        }
    },

    // Update board (silent = true для автообновления превью без уведомления)
    updateBoard: async (id: string, data: BoardUpdate, silent = false) => {
        if (!silent) set({ isLoading: true, error: null })
        try {
            const response = await boardsAPI.update(id, data)
            const updatedBoard = response.data

            set((state) => ({
                boards: state.boards.map((b) => (b.id === id ? { ...b, ...updatedBoard } : b)),
                currentBoard: state.currentBoard?.id === id ? updatedBoard : state.currentBoard,
                isLoading: false,
            }))

            if (!silent) notify.success('Доска обновлена', { title: 'Успех' })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось обновить доску'
            set({ error: message, isLoading: false })
            if (!silent) notify.error(message, { title: 'Ошибка обновления' })
        }
    },

    // Delete board
    deleteBoard: async (id: string) => {
        set({ isLoading: true, error: null })
        try {
            await boardsAPI.delete(id)

            set((state) => ({
                boards: state.boards.filter((b) => b.id !== id),
                currentBoard: state.currentBoard?.id === id ? null : state.currentBoard,
                widgetNodes: state.currentBoard?.id === id ? [] : state.widgetNodes,
                commentNodes: state.currentBoard?.id === id ? [] : state.commentNodes,
                sourceNodes: state.currentBoard?.id === id ? [] : state.sourceNodes,
                contentNodes: state.currentBoard?.id === id ? [] : state.contentNodes,
                edges: state.currentBoard?.id === id ? [] : state.edges,
                isLoading: false,
            }))

            notify.success('Доска удалена', { title: 'Успех' })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось удалить доску'
            set({ error: message, isLoading: false })
            notify.error(message, { title: 'Ошибка удаления' })
        }
    },

    // Set current board
    setCurrentBoard: (board: Board | null) => {
        set({
            currentBoard: board,
            widgetNodes: [],
            commentNodes: [],
            sourceNodes: [],
            contentNodes: [],
            edges: []
        })
    },

    // ============================================
    // WidgetNode Actions
    // ============================================

    fetchWidgetNodes: async (boardId: string) => {
        try {
            const response = await widgetNodesAPI.list(boardId)
            const fetchedNodes = response.data || []

            // Check for duplicates in the fetched data
            const fetchedIds = fetchedNodes.map((n: WidgetNode) => n.id)
            const uniqueFetchedIds = new Set(fetchedIds)
            if (fetchedIds.length !== uniqueFetchedIds.size) {
                console.warn('⚠️ API returned duplicate WidgetNodes!', {
                    total: fetchedIds.length,
                    unique: uniqueFetchedIds.size
                })
            }

            // Deduplicate fetched nodes first
            const deduplicatedFetched = Array.from(
                new Map(fetchedNodes.map((n: WidgetNode) => [n.id, n])).values()
            )

            // Replace with fresh data from backend (handles deletions correctly)
            set({ widgetNodes: deduplicatedFetched })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось загрузить WidgetNode'
            notify.error(message, { title: 'Ошибка загрузки WidgetNode' })
        }
    },

    createWidgetNode: async (boardId: string, data: WidgetNodeCreate) => {
        try {
            const response = await widgetNodesAPI.create(boardId, data)
            const newNode = response.data

            // Don't add to local state - Socket.IO event will handle it

            notify.success('WidgetNode добавлен', { title: 'Успех' })
            return newNode
        } catch (error: any) {
            let message = 'Не удалось создать WidgetNode'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            }
            console.error('createWidgetNode error:', error, 'data:', data)
            notify.error(message, { title: 'Ошибка создания' })
            return null
        }
    },

    duplicateWidgetNode: async (widget: WidgetNode) => {
        const boardId = widget.board_id
        const state = get()
        const fromConfig = widget.config?.sourceContentNodeId as string | undefined
        const fromEdge = state.edges.find(
            (e) => e.target_node_id === widget.id && e.edge_type === 'VISUALIZATION'
        )
        const sourceId = fromConfig || fromEdge?.source_node_id
        if (!sourceId) {
            notify.error('Не удалось определить исходный узел данных для копии виджета', {
                title: 'Ошибка',
            })
            return null
        }
        const isSource = state.sourceNodes.some((n) => n.id === sourceId)
        const sourceNodeType = isSource ? 'SourceNode' : 'ContentNode'
        const offset = 48
        const x = Math.round((widget.x ?? 0) + offset)
        const y = Math.round((widget.y ?? 0) + offset)
        const baseName = widget.name?.trim() ? widget.name.trim() : 'Виджет'
        const copySuffix = ' (копия)'
        const newName =
            baseName.length + copySuffix.length > 200
                ? `${baseName.slice(0, 200 - copySuffix.length)}${copySuffix}`
                : `${baseName}${copySuffix}`

        try {
            const cfg = widget.config ? { ...widget.config } : {}
            if (!cfg.sourceContentNodeId) {
                cfg.sourceContentNodeId = sourceId
            }

            const response = await widgetNodesAPI.create(boardId, {
                name: newName,
                description: widget.description || '',
                html_code: widget.html_code || '',
                css_code: widget.css_code ?? undefined,
                js_code: widget.js_code ?? undefined,
                config: cfg,
                x,
                y,
                width: widget.width ?? undefined,
                height: widget.height ?? undefined,
                auto_refresh: widget.auto_refresh,
                refresh_interval: widget.refresh_interval ?? undefined,
                generated_by: widget.generated_by ?? undefined,
                generation_prompt: widget.generation_prompt ?? undefined,
            })
            const newWidget = response.data

            await edgesAPI.create(boardId, {
                source_node_id: sourceId,
                target_node_id: newWidget.id,
                source_node_type: sourceNodeType,
                target_node_type: 'WidgetNode',
                edge_type: EdgeType.VISUALIZATION,
                label: `Visualizes: ${newWidget.name}`,
            })

            await Promise.all([get().fetchWidgetNodes(boardId), get().fetchEdges(boardId)])
            notify.success('Копия виджета создана', { title: 'Успех' })
            return newWidget
        } catch (error: any) {
            let message = 'Не удалось создать копию виджета'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            }
            console.error('duplicateWidgetNode error:', error)
            notify.error(message, { title: 'Ошибка' })
            return null
        }
    },

    updateWidgetNode: async (boardId: string, widgetNodeId: string, data: WidgetNodeUpdate) => {
        try {
            const response = await widgetNodesAPI.update(boardId, widgetNodeId, data)
            const updatedNode = response.data

            set((state) => ({
                widgetNodes: state.widgetNodes.map((n) => (n.id === widgetNodeId ? updatedNode : n)),
            }))
        } catch (error: any) {
            let message = 'Не удалось обновить WidgetNode'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            }
            console.error('updateWidgetNode error:', error, 'data:', data)
            notify.error(message, { title: 'Ошибка обновления' })
        }
    },

    deleteWidgetNode: async (boardId: string, widgetNodeId: string, explicitProjectId?: string) => {
        try {
            await widgetNodesAPI.delete(boardId, widgetNodeId)

            set((state) => ({
                widgetNodes: state.widgetNodes.filter((n) => n.id !== widgetNodeId),
            }))

            // Remove from project library (use explicit projectId if provided, fallback to current board)
            const projectId = explicitProjectId || get().currentBoard?.project_id
            if (projectId) {
                useLibraryStore.getState().removeWidgetByNodeId(projectId, widgetNodeId)
            }

            notify.success('WidgetNode удален', { title: 'Успех' })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось удалить WidgetNode'
            notify.error(message, { title: 'Ошибка удаления' })
        }
    },

    // ============================================
    // CommentNode Actions
    // ============================================

    fetchCommentNodes: async (boardId: string) => {
        try {
            const response = await commentNodesAPI.list(boardId)
            const fetchedNodes = response.data || []

            // Check for duplicates in the fetched data
            const fetchedIds = fetchedNodes.map((n: CommentNode) => n.id)
            const uniqueFetchedIds = new Set(fetchedIds)
            if (fetchedIds.length !== uniqueFetchedIds.size) {
                console.warn('⚠️ API returned duplicate CommentNodes!', {
                    total: fetchedIds.length,
                    unique: uniqueFetchedIds.size
                })
            }

            // Deduplicate fetched nodes first
            const deduplicatedFetched = Array.from(
                new Map(fetchedNodes.map((n: CommentNode) => [n.id, n])).values()
            )

            // Merge with existing nodes
            set((state) => {
                const existingIds = new Set(state.commentNodes.map(n => n.id))
                const newNodes = deduplicatedFetched.filter((n: CommentNode) => !existingIds.has(n.id))
                const mergedNodes = [...state.commentNodes.map(existing => {
                    const fetched = deduplicatedFetched.find((f: CommentNode) => f.id === existing.id)
                    return fetched || existing
                }), ...newNodes]

                return { commentNodes: mergedNodes }
            })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось загрузить CommentNode'
            notify.error(message, { title: 'Ошибка загрузки CommentNode' })
        }
    },

    createCommentNode: async (boardId: string, data: CommentNodeCreate) => {
        try {
            const response = await commentNodesAPI.create(boardId, data)
            const newNode = response.data

            // Don't add to local state - Socket.IO event will handle it

            notify.success('CommentNode добавлен', { title: 'Успех' })
            return newNode
        } catch (error: any) {
            let message = 'Не удалось создать CommentNode'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            }
            console.error('createCommentNode error:', error, 'data:', data)
            notify.error(message, { title: 'Ошибка создания' })
            return null
        }
    },

    updateCommentNode: async (boardId: string, commentNodeId: string, data: CommentNodeUpdate) => {
        try {
            const response = await commentNodesAPI.update(boardId, commentNodeId, data)
            const updatedNode = response.data

            set((state) => ({
                commentNodes: state.commentNodes.map((n) => (n.id === commentNodeId ? updatedNode : n)),
            }))
        } catch (error: any) {
            let message = 'Не удалось обновить CommentNode'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            }
            console.error('updateCommentNode error:', error, 'data:', data)
            notify.error(message, { title: 'Ошибка обновления' })
        }
    },

    deleteCommentNode: async (boardId: string, commentNodeId: string) => {
        try {
            await commentNodesAPI.delete(boardId, commentNodeId)

            set((state) => ({
                commentNodes: state.commentNodes.filter((n) => n.id !== commentNodeId),
            }))

            notify.success('CommentNode удален', { title: 'Успех' })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось удалить CommentNode'
            notify.error(message, { title: 'Ошибка удаления' })
        }
    },

    resolveCommentNode: async (boardId: string, commentNodeId: string, isResolved: boolean) => {
        try {
            const response = await commentNodesAPI.resolve(boardId, commentNodeId, isResolved)
            const updatedNode = response.data

            set((state) => ({
                commentNodes: state.commentNodes.map((n) => (n.id === commentNodeId ? updatedNode : n)),
            }))

            notify.success(
                isResolved ? 'Комментарий отмечен как решенный' : 'Комментарий отмечен как нерешенный',
                { title: 'Успех' }
            )
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось обновить статус комментария'
            notify.error(message, { title: 'Ошибка обновления' })
        }
    },

    // ============================================
    // SourceNode Actions
    // ============================================

    fetchSourceNodes: async (boardId: string) => {
        try {
            const response = await sourceNodesAPI.list(boardId)
            const fetchedNodes = response.data || []

            const deduplicatedFetched = Array.from(
                new Map(fetchedNodes.map((n: SourceNode) => [n.id, n])).values()
            )

            set((state) => {
                const existingIds = new Set(state.sourceNodes.map(n => n.id))
                const newNodes = deduplicatedFetched.filter((n: SourceNode) => !existingIds.has(n.id))
                const mergedNodes = [...state.sourceNodes.map(existing => {
                    const fetched = deduplicatedFetched.find((f: SourceNode) => f.id === existing.id)
                    return fetched || existing
                }), ...newNodes]

                return { sourceNodes: mergedNodes }
            })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось загрузить SourceNode'
            notify.error(message, { title: 'Ошибка загрузки SourceNode' })
        }
    },

    createSourceNode: async (boardId: string, data: SourceNodeCreate) => {
        try {
            console.log('[boardStore] createSourceNode - sending data:', {
                'metadata': data.metadata,
                'metadata?.name': data.metadata?.name,
                'source_type': data.source_type,
            })
            const response = await sourceNodesAPI.create({ ...data, board_id: boardId })
            const newNode = response.data

            // Strategic logging for SourceNode naming
            console.log('[boardStore] createSourceNode - response:', {
                'metadata': newNode?.metadata,
                'metadata?.name': newNode?.metadata?.name,
                'node_metadata': (newNode as any)?.node_metadata,
                'response keys': newNode ? Object.keys(newNode) : '<null>',
            })

            set((state) => ({
                sourceNodes: [...state.sourceNodes, newNode],
            }))

            notify.success('SourceNode добавлен', { title: 'Успех' })
            return newNode
        } catch (error: any) {
            let message = 'Не удалось создать SourceNode'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            } else if (!error.response && import.meta.env.DEV) {
                message +=
                    ' Если API в Docker без порта 8000: откройте UI на том же origin, что и nginx (например :3000), либо запустите Vite с VITE_DEV_PROXY_TARGET=http://localhost:3000 (см. run-frontend.ps1 -DockerNginx).'
            }
            console.error('createSourceNode error:', error, 'data:', data)
            notify.error(message, { title: 'Ошибка создания' })
            return null
        }
    },

    updateSourceNode: async (sourceNodeId: string, data: SourceNodeUpdate) => {
        try {
            const response = await sourceNodesAPI.update(sourceNodeId, data)
            const updatedNode = response.data

            set((state) => ({
                sourceNodes: state.sourceNodes.map((n) => (n.id === sourceNodeId ? updatedNode : n)),
            }))

            // Don't show notification for position/size updates (too noisy)
            // notify.success('SourceNode обновлен', { title: 'Успех' })
        } catch (error: any) {
            let message = 'Не удалось обновить SourceNode'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            }
            console.error('updateSourceNode error:', error, 'data:', data)
            notify.error(message, { title: 'Ошибка обновления' })
        }
    },

    deleteSourceNode: async (sourceNodeId: string) => {
        try {
            await sourceNodesAPI.delete(sourceNodeId)

            set((state) => ({
                sourceNodes: state.sourceNodes.filter((n) => n.id !== sourceNodeId),
            }))

            notify.success('SourceNode удален', { title: 'Успех' })

            // Refresh project tree (Таблицы, Измерения sections in ProjectExplorer)
            const projectId = get().currentBoard?.project_id
            if (projectId) {
                const boards = get().boards.filter(b => b.project_id === projectId)
                useLibraryStore.getState().refreshProjectTree(projectId, boards)
            }
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось удалить SourceNode'
            notify.error(message, { title: 'Ошибка удаления' })
        }
    },

    validateSourceNode: async (sourceNodeId: string): Promise<boolean> => {
        try {
            const response = await sourceNodesAPI.validate(sourceNodeId)
            const isValid = response.data?.valid || false

            if (isValid) {
                notify.success('Источник данных валиден', { title: 'Валидация' })
            } else {
                const errors = response.data?.errors?.join(', ') || 'Неизвестная ошибка'
                notify.error(`Источник невалиден: ${errors}`, { title: 'Валидация' })
            }

            return isValid
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось провалидировать SourceNode'
            notify.error(message, { title: 'Ошибка валидации' })
            return false
        }
    },

    extractFromSource: async (sourceNodeId: string, params?: Record<string, any>): Promise<ContentNode | null> => {
        const boardId = get().currentBoard?.id
        if (!boardId) {
            notify.error('Доска не выбрана', { title: 'Ошибка' })
            return null
        }

        try {
            console.log('🔄 Starting extraction for source:', sourceNodeId)
            const response = await sourceNodesAPI.extract(boardId, sourceNodeId, params)
            console.log('📦 Extraction response:', response.data)

            // Response format: { content_node, extract_edge, summary }
            const contentNodeId = response.data.content_node?.id || response.data.content_node_id
            if (contentNodeId) {
                console.log('📥 Fetching ContentNode:', contentNodeId)
                // Fetch the created ContentNode
                const contentNodeRes = await contentNodesAPI.get(contentNodeId)
                const newContentNode = contentNodeRes.data
                console.log('✅ Got ContentNode:', newContentNode)

                // Reload edges to get EXTRACT edge
                await get().fetchEdges(boardId)

                // Add ContentNode to store
                set((state) => ({
                    contentNodes: [...state.contentNodes, newContentNode],
                }))

                // Refresh project tree (Таблицы, Измерения appear in ProjectExplorer)
                const projectId = get().currentBoard?.project_id
                if (projectId) {
                    const boards = get().boards.filter(b => b.project_id === projectId)
                    useLibraryStore.getState().refreshProjectTree(projectId, boards)
                }

                notify.success('Данные успешно извлечены из источника', { title: 'Успех' })
                return newContentNode
            }

            console.warn('⚠️ No content_node_id in response:', response.data)

            return null
        } catch (error: any) {
            console.error('❌ Extraction error full:', error)
            console.error('❌ error.response:', error.response)
            console.error('❌ error.response?.data:', error.response?.data)
            console.error('❌ error.message:', error.message)

            let message = 'Не удалось извлечь данные из источника'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (typeof detail === 'string') {
                    message = detail
                } else if (Array.isArray(detail)) {
                    // Pydantic validation errors
                    message = detail.map((err: any) => err.msg || err.message || JSON.stringify(err)).join(', ')
                } else if (detail.errors && Array.isArray(detail.errors)) {
                    // Backend extraction errors
                    message = detail.errors.join('; ')
                } else if (detail.message) {
                    message = detail.message
                } else {
                    message = JSON.stringify(detail)
                }
            } else if (error.message) {
                message = error.message
            }
            console.error('Extraction error:', error.response?.data)
            notify.error(message, { title: 'Ошибка извлечения' })
            return null
        }
    },

    refreshSourceNode: async (sourceNodeId: string) => {
        try {
            const response = await sourceNodesAPI.refresh(sourceNodeId)
            const updatedSource = response.data

            // Update in store
            set((state) => ({
                sourceNodes: state.sourceNodes.map((node) =>
                    node.id === sourceNodeId ? updatedSource : node
                ),
            }))

            notify.success('Данные успешно обновлены', { title: 'Источник обновлён' })
        } catch (error: any) {
            let message = 'Не удалось обновить источник'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (typeof detail === 'string') {
                    message = detail
                } else if (Array.isArray(detail)) {
                    message = detail.map((err: any) => err.msg || err.message || JSON.stringify(err)).join(', ')
                } else if (detail.message) {
                    message = detail.message
                } else {
                    message = JSON.stringify(detail)
                }
            }
            notify.error(message, { title: 'Ошибка обновления' })
        }
    },

    // ============================================
    // ContentNode Actions
    // ============================================

    fetchContentNodes: async (boardId: string) => {
        try {
            const response = await contentNodesAPI.list(boardId)
            const fetchedNodes = response.data || []

            const deduplicatedFetched = Array.from(
                new Map(fetchedNodes.map((n: ContentNode) => [n.id, n])).values()
            )

            // Replace with fetched nodes (don't merge with existing to handle deletions)
            set({ contentNodes: deduplicatedFetched })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось загрузить ContentNode'
            notify.error(message, { title: 'Ошибка загрузки ContentNode' })
        }
    },

    createContentNode: async (boardId: string, data: ContentNodeCreate) => {
        try {
            const response = await contentNodesAPI.create({ ...data, board_id: boardId })
            const newNode = response.data

            set((state) => ({
                contentNodes: [...state.contentNodes, newNode],
            }))

            notify.success('ContentNode добавлен', { title: 'Успех' })
            return newNode
        } catch (error: any) {
            let message = 'Не удалось создать ContentNode'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            }
            console.error('createContentNode error:', error, 'data:', data)
            notify.error(message, { title: 'Ошибка создания' })
            return null
        }
    },

    duplicateContentNode: async (node: ContentNode) => {
        const boardId = get().currentBoard?.id
        if (!boardId) {
            notify.error('Доска не выбрана', { title: 'Ошибка' })
            return null
        }

        await get().fetchEdges(boardId)
        const st = get()
        const transformationSources = getTransformationSourcesForDuplicate(
            node,
            st.edges,
            st.sourceNodes,
            st.contentNodes
        )

        const offset = 48
        const pos = node.position || { x: 0, y: 0 }
        const metaName = node.metadata?.name
        const tableName = node.content?.tables?.[0]?.name
        const baseTitle = (metaName || tableName || 'Узел данных').trim() || 'Узел данных'
        const copySuffix = ' (копия)'
        const newName =
            baseTitle.length + copySuffix.length > 500
                ? `${baseTitle.slice(0, 500 - copySuffix.length)}${copySuffix}`
                : `${baseTitle}${copySuffix}`

        const content = JSON.parse(JSON.stringify(node.content ?? { text: '', tables: [] }))
        const lineage = JSON.parse(
            JSON.stringify(
                node.lineage ?? {
                    operation: 'copy',
                    timestamp: new Date().toISOString(),
                }
            )
        )
        const metadata = JSON.parse(JSON.stringify(node.metadata ?? {}))
        metadata.name = newName

        try {
            const response = await contentNodesAPI.create({
                board_id: boardId,
                content,
                lineage,
                metadata,
                position: { x: pos.x + offset, y: pos.y + offset },
            })
            const newNode = response.data

            set((state) => ({
                contentNodes: [...state.contentNodes, newNode],
            }))

            for (const src of transformationSources) {
                const t = src.template
                const sourceType = t ? t.source_node_type : src.sourceType
                await edgesAPI.create(boardId, {
                    source_node_id: src.sourceId,
                    source_node_type: sourceType,
                    target_node_id: newNode.id,
                    target_node_type: 'content_node',
                    edge_type: EdgeType.TRANSFORMATION,
                    label: t?.label ?? undefined,
                    parameter_mapping: t?.parameter_mapping ?? undefined,
                    transformation_code: t?.transformation_code ?? undefined,
                    transformation_params: t?.transformation_params
                        ? { ...t.transformation_params }
                        : { duplicated_from_content_node_id: node.id },
                    visual_config: t?.visual_config ?? undefined,
                })
            }

            await get().fetchEdges(boardId)

            const projectId = get().currentBoard?.project_id
            if (projectId) {
                const boards = get().boards.filter((b) => b.project_id === projectId)
                useLibraryStore.getState().refreshProjectTree(projectId, boards)
            }

            notify.success('Копия узла данных создана', { title: 'Успех' })
            return newNode
        } catch (error: any) {
            let message = 'Не удалось создать копию узла данных'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            }
            console.error('duplicateContentNode error:', error)
            notify.error(message, { title: 'Ошибка' })
            return null
        }
    },

    updateContentNode: async (contentNodeId: string, data: ContentNodeUpdate) => {
        try {
            console.log('📤 Updating ContentNode:', { contentNodeId, data })
            const response = await contentNodesAPI.update(contentNodeId, data)
            const updatedNode = response.data
            console.log('✅ ContentNode updated:', updatedNode)

            set((state) => ({
                contentNodes: state.contentNodes.map((n) => (n.id === contentNodeId ? updatedNode : n)),
            }))

            // Don't show notification for position/size updates (too noisy)
            // notify.success('ContentNode обновлен', { title: 'Успех' })
        } catch (error: any) {
            let message = 'Не удалось обновить ContentNode'
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail
                if (Array.isArray(detail)) {
                    message = detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                } else if (typeof detail === 'string') {
                    message = detail
                }
            }
            console.error('updateContentNode error:', error, 'data:', data)
            notify.error(message, { title: 'Ошибка обновления' })
        }
    },

    deleteContentNode: async (contentNodeId: string) => {
        try {
            const state = get()
            const boardId = state.currentBoard?.id

            if (!boardId) {
                throw new Error('No active board')
            }

            await contentNodesAPI.delete(contentNodeId)

            // Backend handles cascade deletion, so we need to refetch all nodes
            await Promise.all([
                get().fetchContentNodes(boardId),
                get().fetchWidgetNodes(boardId),
                get().fetchEdges(boardId)
            ])

            notify.success('ContentNode и зависимые узлы удалены', { title: 'Успех' })

            // Refresh project tree (Таблицы, Измерения sections in ProjectExplorer)
            const projectId = get().currentBoard?.project_id
            if (projectId) {
                const boards = get().boards.filter(b => b.project_id === projectId)
                useLibraryStore.getState().refreshProjectTree(projectId, boards)
            }
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось удалить ContentNode'
            notify.error(message, { title: 'Ошибка удаления' })
        }
    },

    getContentTable: async (contentNodeId: string, tableIndex: number) => {
        try {
            const response = await contentNodesAPI.getTable(contentNodeId, String(tableIndex))
            return response.data
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось получить таблицу'
            notify.error(message, { title: 'Ошибка получения таблицы' })
            return null
        }
    },

    getContentLineage: async (contentNodeId: string) => {
        try {
            const response = await contentNodesAPI.getLineage(contentNodeId)
            return response.data
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось получить lineage'
            notify.error(message, { title: 'Ошибка lineage' })
            return null
        }
    },

    getDownstreamContents: async (contentNodeId: string): Promise<ContentNode[]> => {
        try {
            const response = await contentNodesAPI.getDownstream(contentNodeId)
            return response.data || []
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось получить downstream узлы'
            notify.error(message, { title: 'Ошибка получения зависимостей' })
            return []
        }
    },

    transformContent: async (contentNodeId: string, prompt: string, code?: string, transformationId?: string, targetNodeId?: string, chatHistory?: Array<{ role: string; content: string }>): Promise<ContentNode | null> => {
        try {
            const state = get()
            const boardId = state.currentBoard?.id
            if (!boardId) {
                throw new Error('No active board')
            }

            // If code is provided, call execute endpoint (Step 2)
            // Otherwise, call the old single-step endpoint (backward compatibility)
            let response
            if (code) {
                response = await contentNodesAPI.transformExecute(boardId, contentNodeId, {
                    code,
                    transformation_id: transformationId,
                    description: prompt,
                    prompt: prompt,  // Save for editing later
                    chat_history: chatHistory,  // Save chat history for editing later
                    target_node_id: targetNodeId,  // If provided, UPDATE existing node
                })
            } else {
                response = await contentNodesAPI.transformSingle(boardId, contentNodeId, { prompt })
            }

            const contentNode = response.data.content_node
            const transformEdge = response.data.transform_edge
            const isUpdate = response.data.updated === true

            // Strategic logging for ContentNode naming pipeline
            console.log('[boardStore] transformContent response:', {
                'contentNode.metadata': contentNode?.metadata,
                'contentNode.metadata?.name': contentNode?.metadata?.name,
                'contentNode.node_metadata': contentNode?.node_metadata,
                'isUpdate': isUpdate,
                'response.data keys': Object.keys(response.data),
                'contentNode keys': contentNode ? Object.keys(contentNode) : '<null>',
            })

            if (isUpdate) {
                // UPDATE mode: replace existing node in array
                set((state) => ({
                    contentNodes: state.contentNodes.map(n => n.id === contentNode.id ? contentNode : n),
                    edges: state.edges.map(e => {
                        // Update edge if it's a transformation edge to this node
                        if (e.target_node_id === contentNode.id && e.edge_type === 'TRANSFORMATION') {
                            return transformEdge || e
                        }
                        return e
                    })
                }))
                notify.success('Обработка обновлена', { title: 'Успех' })
            } else {
                // CREATE mode: add new node
                set((state) => ({
                    contentNodes: [...state.contentNodes, contentNode],
                    edges: transformEdge ? [...state.edges, transformEdge] : state.edges,
                }))
                notify.success('Обработка создана', { title: 'Успех' })
            }

            return contentNode
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Transformation failed'
            notify.error(message, { title: 'Transformation Error' })
            return null
        }
    },

    transformContents: async (sourceContentIds: string[], code: string, description?: string, position?: { x: number, y: number }): Promise<ContentNode | null> => {
        try {
            // 1. Execute transform — backend creates ContentNode and returns only its id
            const response = await contentNodesAPI.transform(sourceContentIds, code, description)
            const { content_node_id } = response.data as any

            // 2. Fetch the full ContentNode
            const contentNodeRes = await contentNodesAPI.get(content_node_id)
            const newContentNode = contentNodeRes.data

            // 3. Update canvas position if provided
            if (position) {
                await contentNodesAPI.update(content_node_id, { position })
                newContentNode.position = position
            }

            // 4. Add to board state
            set((state) => ({
                contentNodes: [...state.contentNodes, newContentNode],
            }))

            // 5. Refresh edges (backend auto-creates TRANSFORMATION edge)
            const boardId = get().currentBoard?.id
            if (boardId) {
                get().fetchEdges(boardId)
            }

            // 6. Refresh project tree (Таблицы, Измерения sections in ProjectExplorer)
            const projectId = get().currentBoard?.project_id
            if (projectId) {
                const boards = get().boards.filter(b => b.project_id === projectId)
                useLibraryStore.getState().refreshProjectTree(projectId, boards)
            }

            notify.success('Обработка выполнена', { title: 'Успех' })
            return newContentNode
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось выполнить трансформацию'
            notify.error(message, { title: 'Ошибка трансформации' })
            return null
        }
    },

    visualizeContent: async (contentNodeId: string, params: {
        user_prompt?: string
        widget_name?: string
        auto_refresh?: boolean
    }): Promise<void> => {
        try {
            const state = get()
            const boardId = state.currentBoard?.id
            if (!boardId) {
                throw new Error('No active board')
            }

            notify.info('Генерация визуализации...', { title: 'AI Visualizer' })

            const response = await contentNodesAPI.visualize(contentNodeId, params)
            const result = response.data

            if (result.status === 'error') {
                throw new Error(result.error || 'Visualization failed')
            }

            // Refresh board data to get new widget node and edge
            await Promise.all([
                get().fetchWidgetNodes(boardId),
                get().fetchEdges(boardId),
            ])

            // Auto-save new widget to library (safety net if socket is disconnected)
            const widgetNodeId = result.widget_node_id
            if (widgetNodeId) {
                const newWidget = get().widgetNodes.find(w => w.id === widgetNodeId)
                const projectId = state.currentBoard?.project_id
                if (newWidget && projectId && newWidget.html_code) {
                    useLibraryStore.getState().syncWidgetToLibrary(projectId, newWidget.id, newWidget.board_id, {
                        name: newWidget.name,
                        description: newWidget.description,
                        html_code: newWidget.html_code,
                        css_code: newWidget.css_code,
                        js_code: newWidget.js_code,
                        widget_type: newWidget.config?.widget_type,
                        source_content_node_id: newWidget.config?.sourceContentNodeId,
                    })
                }
            }

            notify.success('Визуализация создана', { title: 'Успех' })
        } catch (error: any) {
            const message = error.response?.data?.detail || error.message || 'Не удалось создать визуализацию'
            notify.error(message, { title: 'Ошибка визуализации' })
        }
    },

    // ============================================
    // Edge Actions
    // ============================================

    fetchEdges: async (boardId: string) => {
        try {
            const response = await edgesAPI.list(boardId)
            console.log('Fetched edges response:', response.data)
            const edges = response.data?.edges || response.data || []
            set({ edges: Array.isArray(edges) ? edges : [] })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось загрузить связи'
            console.error('fetchEdges error:', error)
            set({ edges: [] })
            notify.error(message, { title: 'Ошибка загрузки связей' })
        }
    },

    createEdge: async (boardId: string, data: EdgeCreate) => {
        try {
            const response = await edgesAPI.create(boardId, data)
            const newEdge = response.data

            set((state) => ({
                edges: [...(state.edges || []), newEdge],
            }))

            notify.success('Связь создана', { title: 'Успех' })
            return newEdge
        } catch (error: any) {
            let message = 'Не удалось создать связь'

            if (error.response?.data?.detail?.errors) {
                const errors = error.response.data.detail.errors
                message = errors.join(', ')
            } else if (error.response?.data?.detail) {
                message = error.response.data.detail
            }

            console.error('createEdge error:', error)
            notify.error(message, { title: 'Ошибка создания связи' })
            return null
        }
    },

    updateEdge: async (boardId: string, edgeId: string, data: EdgeUpdate) => {
        try {
            const response = await edgesAPI.update(boardId, edgeId, data)
            const updatedEdge = response.data

            set((state) => ({
                edges: state.edges.map((e) => (e.id === edgeId ? updatedEdge : e)),
            }))

            notify.success('Связь обновлена', { title: 'Успех' })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось обновить связь'
            notify.error(message, { title: 'Ошибка обновления связи' })
        }
    },

    deleteEdge: async (boardId: string, edgeId: string) => {
        try {
            await edgesAPI.delete(boardId, edgeId)

            set((state) => ({
                edges: state.edges.filter((e) => e.id !== edgeId),
            }))

            notify.success('Связь удалена', { title: 'Успех' })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось удалить связь'
            notify.error(message, { title: 'Ошибка удаления связи' })
        }
    },

    // Clear error
    clearError: () => {
        set({ error: null })
    },

    // Clear board data (nodes and edges)
    clearBoardData: () => {
        set({
            widgetNodes: [],
            commentNodes: [],
            sourceNodes: [],
            contentNodes: [],
            edges: []
        })
    },
}))
