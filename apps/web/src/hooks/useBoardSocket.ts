/**
 * WebSocket hook for real-time board collaboration
 */
import { useEffect, useRef, useCallback } from 'react'
import { io, Socket } from 'socket.io-client'
import { useBoardStore } from '@/store/boardStore'
import type { WidgetNode, CommentNode, Edge } from '@/types'

const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function useBoardSocket(boardId: string | undefined) {
    const socketRef = useRef<Socket | null>(null)
    const {
        widgetNodes,
        commentNodes,
        edges,
    } = useBoardStore()

    // Connect to Socket.IO server and setup all event listeners
    useEffect(() => {
        if (!boardId) return

        console.log('🔗 Connecting to Socket.IO server...')
        const socket = io(SOCKET_URL, {
            path: '/socket.io',
            transports: ['polling', 'websocket'],
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: 5,
            autoConnect: true,
        })

        socketRef.current = socket

        // Setup event handlers that will be registered when connected
        const setupEventHandlers = () => {
            console.log('🎯 Setting up event handlers on connected socket:', socket.id)

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
            }

            const handleWidgetNodeDeleted = (data: { id: string }) => {
                console.log('📡 Received widget_node_deleted:', data.id)
                useBoardStore.setState((state) => ({
                    widgetNodes: state.widgetNodes.filter((n) => n.id !== data.id),
                }))
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
            socket.on('widget_node_created', handleWidgetNodeCreated)
            socket.on('widget_node_updated', handleWidgetNodeUpdated)
            socket.on('widget_node_deleted', handleWidgetNodeDeleted)

            socket.on('comment_node_created', handleCommentNodeCreated)
            socket.on('comment_node_updated', handleCommentNodeUpdated)
            socket.on('comment_node_deleted', handleCommentNodeDeleted)

            socket.on('edge_created', handleEdgeCreated)
            socket.on('edge_updated', handleEdgeUpdated)
            socket.on('edge_deleted', handleEdgeDeleted)
        }

        socket.on('connect', () => {
            console.log('✅ Connected to Socket.IO server:', socket.id)
            // Join board room
            socket.emit('join_board', { board_id: boardId })
            // Setup event handlers after connection
            setupEventHandlers()
        })

        socket.on('joined_board', (data: { board_id: string }) => {
            console.log('📌 Joined board:', data.board_id)
        })

        socket.on('disconnect', () => {
            console.log('🔌 Disconnected from Socket.IO server')
        })

        socket.on('connect_error', (error) => {
            console.error('❌ Socket.IO connection error:', error)
        })

        // Cleanup
        return () => {
            if (boardId) {
                socket.emit('leave_board', { board_id: boardId })
            }
            socket.disconnect()
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
        socket: socketRef.current,
        emitEvent,
        isConnected: socketRef.current?.connected || false,
    }
}
