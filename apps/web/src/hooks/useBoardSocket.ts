/**
 * WebSocket hook for real-time board collaboration
 */
import { useEffect, useRef, useCallback, useState } from 'react'
import { io, Socket } from 'socket.io-client'
import { useBoardStore } from '@/store/boardStore'
import { useLibraryStore } from '@/store/libraryStore'
import type { WidgetNode, CommentNode, Edge } from '@/types'
import { getSocketIoUrl, SOCKET_IO_CLIENT_OPTIONS, logSocketIoConnectError } from '@/config/apiBase'

export function useBoardSocket(boardId: string | undefined) {
    const socketRef = useRef<Socket | null>(null)
    /** Без useState дочерние компоненты не узнают о сокете после mount (ref не триггерит ререндер). */
    const [socket, setSocket] = useState<Socket | null>(null)
    const [isConnected, setIsConnected] = useState(false)
    const {
        widgetNodes,
        commentNodes,
        edges,
    } = useBoardStore()

    // Connect to Socket.IO server and setup all event listeners
    useEffect(() => {
        if (!boardId) return

        const socketUrl = getSocketIoUrl()
        if (import.meta.env.DEV) {
            console.log('🔗 Connecting to Socket.IO server...', socketUrl)
        } else {
            console.log('🔗 Connecting to Socket.IO server...')
        }
        const ioSocket = io(socketUrl, { ...SOCKET_IO_CLIENT_OPTIONS })

        socketRef.current = ioSocket
        setSocket(ioSocket)

        // Регистрируем обработчики один раз на экземпляр (не на каждый reconnect).
        const setupEventHandlers = () => {
            console.log('🎯 Setting up event handlers on socket:', ioSocket.id)

            // WidgetNode events
            const handleWidgetNodeCreated = (node: WidgetNode) => {
                console.log('📡 Received widget_node_created:', node)
                useBoardStore.setState((state) => {
                    // Check if node already exists (avoid duplicates from optimistic updates)
                    const existingIndex = state.widgetNodes.findIndex(n => n.id === node.id)
                    if (existingIndex !== -1) {
                        console.log('📌 WidgetNode already exists, updating with server data:', node.id)
                        // Update existing node with server data
                        const updatedNodes = [...state.widgetNodes]
                        updatedNodes[existingIndex] = {
                            ...updatedNodes[existingIndex],
                            ...node
                        }
                        return { widgetNodes: updatedNodes }
                    }
                    // Node doesn't exist, add it (for other users)
                    console.log('📌 Adding new WidgetNode from socket:', node.id)
                    return {
                        widgetNodes: [...state.widgetNodes, node]
                    }
                })

                // Auto-save widget to project library
                const projectId = useBoardStore.getState().currentBoard?.project_id
                if (projectId && node.html_code) {
                    useLibraryStore.getState().syncWidgetToLibrary(projectId, node.id, node.board_id, {
                        name: node.name,
                        description: node.description,
                        html_code: node.html_code,
                        css_code: node.css_code,
                        js_code: node.js_code,
                        widget_type: node.config?.widget_type,
                        source_content_node_id: node.config?.sourceContentNodeId,
                    })
                }
            }

            const handleWidgetNodeUpdated = (node: WidgetNode) => {
                console.log('📡 Received widget_node_updated:', node)
                useBoardStore.setState((state) => {
                    // Only update if node exists (don't re-add deleted nodes)
                    const exists = state.widgetNodes.some(n => n.id === node.id)
                    if (!exists) {
                        console.log('⚠️ Ignoring update for deleted WidgetNode:', node.id)
                        return state
                    }
                    return {
                        widgetNodes: state.widgetNodes.map((n) => (n.id === node.id ? node : n))
                    }
                })

                // Auto-update library copy
                const projectId = useBoardStore.getState().currentBoard?.project_id
                if (projectId && node.html_code) {
                    useLibraryStore.getState().syncWidgetToLibrary(projectId, node.id, node.board_id, {
                        name: node.name,
                        description: node.description,
                        html_code: node.html_code,
                        css_code: node.css_code,
                        js_code: node.js_code,
                        widget_type: node.config?.widget_type,
                        source_content_node_id: node.config?.sourceContentNodeId,
                    })
                }
            }

            const handleWidgetNodeDeleted = (data: { id: string }) => {
                console.log('📡 Received widget_node_deleted:', data.id)
                useBoardStore.setState((state) => ({
                    widgetNodes: state.widgetNodes.filter((n) => n.id !== data.id),
                }))

                // Remove from project library
                const projectId = useBoardStore.getState().currentBoard?.project_id
                if (projectId) {
                    useLibraryStore.getState().removeWidgetByNodeId(projectId, data.id)
                }
            }

            // CommentNode events
            const handleCommentNodeCreated = (node: CommentNode) => {
                console.log('📡 Received comment_node_created:', node)
                useBoardStore.setState((state) => {
                    // Check if node already exists (avoid duplicates from optimistic updates)
                    const existingIndex = state.commentNodes.findIndex(n => n.id === node.id)
                    if (existingIndex !== -1) {
                        console.log('📌 CommentNode already exists, updating with server data:', node.id)
                        // Update existing node with server data
                        const updatedNodes = [...state.commentNodes]
                        updatedNodes[existingIndex] = {
                            ...updatedNodes[existingIndex],
                            ...node
                        }
                        return { commentNodes: updatedNodes }
                    }
                    // Node doesn't exist, add it (for other users)
                    console.log('📌 Adding new CommentNode from socket:', node.id)
                    return {
                        commentNodes: [...state.commentNodes, node]
                    }
                })
            }

            const handleCommentNodeUpdated = (node: CommentNode) => {
                console.log('📡 Received comment_node_updated:', node)
                useBoardStore.setState((state) => {
                    // Only update if node exists (don't re-add deleted nodes)
                    const exists = state.commentNodes.some(n => n.id === node.id)
                    if (!exists) {
                        console.log('⚠️ Ignoring update for deleted CommentNode:', node.id)
                        return state
                    }
                    return {
                        commentNodes: state.commentNodes.map((n) => (n.id === node.id ? node : n))
                    }
                })
            }

            const handleCommentNodeDeleted = (data: { id: string }) => {
                console.log('📡 Received comment_node_deleted:', data.id)
                useBoardStore.setState((state) => ({
                    commentNodes: state.commentNodes.filter((n) => n.id !== data.id),
                }))
            }

            // Edge events
            const handleEdgeCreated = (data: any) => {
                console.log('📡 Received edge_created:', data)
                const edge: Edge = {
                    id: data.id || '',
                    board_id: data.board_id || '',
                    source_node_id: data.source_node_id || '',
                    target_node_id: data.target_node_id || '',
                    source_node_type: data.source_node_type || '',
                    target_node_type: data.target_node_type || '',
                    edge_type: data.edge_type || 'REFERENCE',
                    label: data.label || null,
                    parameter_mapping: data.parameter_mapping || {},
                    transformation_code: data.transformation_code || null,
                    transformation_params: data.transformation_params || {},
                    visual_config: data.visual_config || {},
                    created_at: data.created_at || new Date().toISOString(),
                    updated_at: data.updated_at || new Date().toISOString(),
                    is_valid: data.is_valid || 'true',
                    validation_errors: data.validation_errors || null,
                }
                useBoardStore.setState((state) => ({
                    edges: [...(state.edges || []), edge],
                }))
            }

            const handleEdgeUpdated = (data: any) => {
                console.log('📡 Received edge_updated:', data)
                const edge: Edge = {
                    id: data.id || '',
                    board_id: data.board_id || '',
                    source_node_id: data.source_node_id || '',
                    target_node_id: data.target_node_id || '',
                    source_node_type: data.source_node_type || '',
                    target_node_type: data.target_node_type || '',
                    edge_type: data.edge_type || 'REFERENCE',
                    label: data.label || null,
                    parameter_mapping: data.parameter_mapping || {},
                    transformation_code: data.transformation_code || null,
                    transformation_params: data.transformation_params || {},
                    visual_config: data.visual_config || {},
                    created_at: data.created_at || new Date().toISOString(),
                    updated_at: data.updated_at || new Date().toISOString(),
                    is_valid: data.is_valid || 'true',
                    validation_errors: data.validation_errors || null,
                }
                useBoardStore.setState((state) => ({
                    edges: (state.edges || []).map((e) => (e.id === edge.id ? edge : e)),
                }))
            }

            const handleEdgeDeleted = (data: { id: string }) => {
                console.log('📡 Received edge_deleted:', data.id)
                useBoardStore.setState((state) => ({
                    edges: (state.edges || []).filter((e) => e.id !== data.id),
                }))
            }

            // Register all event handlers
            ioSocket.on('widget_node_created', handleWidgetNodeCreated)
            ioSocket.on('widget_node_updated', handleWidgetNodeUpdated)
            ioSocket.on('widget_node_deleted', handleWidgetNodeDeleted)

            ioSocket.on('comment_node_created', handleCommentNodeCreated)
            ioSocket.on('comment_node_updated', handleCommentNodeUpdated)
            ioSocket.on('comment_node_deleted', handleCommentNodeDeleted)

            ioSocket.on('edge_created', handleEdgeCreated)
            ioSocket.on('edge_updated', handleEdgeUpdated)
            ioSocket.on('edge_deleted', handleEdgeDeleted)
        }

        setupEventHandlers()

        ioSocket.on('connect', () => {
            console.log('✅ Connected to Socket.IO server:', ioSocket.id)
            setIsConnected(true)
            ioSocket.emit('join_board', { board_id: boardId })
        })

        ioSocket.on('joined_board', (data: { board_id: string }) => {
            console.log('📌 Joined board:', data.board_id)
        })

        ioSocket.on('disconnect', () => {
            console.log('🔌 Disconnected from Socket.IO server')
            setIsConnected(false)
        })

        ioSocket.on('connect_error', (error) => {
            logSocketIoConnectError('❌ Socket.IO connection error:', error)
        })

        // Cleanup
        return () => {
            setIsConnected(false)
            setSocket(null)
            if (boardId) {
                ioSocket.emit('leave_board', { board_id: boardId })
            }
            ioSocket.disconnect()
            socketRef.current = null
        }
    }, [boardId])

    // Emit events helper
    const emitEvent = useCallback((eventName: string, data: any) => {
        const socket = socketRef.current
        if (socket && socket.connected) {
            socket.emit(eventName, data)
        }
    }, [])

    return {
        socket,
        emitEvent,
        isConnected,
    }
}
