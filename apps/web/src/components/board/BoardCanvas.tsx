import { useCallback, useState, useEffect } from 'react'
import {
    ReactFlow,
    Background,
    Controls,
    MiniMap,
    Node,
    Edge as ReactFlowEdge,
    NodeChange,
    EdgeChange,
    Connection,
    applyNodeChanges,
    applyEdgeChanges,
    SelectionMode,
    useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useBoardStore } from '@/store/boardStore'
import { useAIAssistantStore } from '@/store/aiAssistantStore'
import { useParams } from 'react-router-dom'
import { WidgetNodeCard } from './WidgetNodeCard'
import { CommentNodeCard } from './CommentNodeCard'
import { SourceNodeCard } from './SourceNodeCard'
import { ContentNodeCard } from './ContentNodeCard'
import { TransformationEdge } from './TransformationEdge'
import { SourceDialogRouter } from '@/components/dialogs/sources'
import { TransformDialog } from '@/components/board/TransformDialog'
import { WidgetDialog } from '@/components/board/WidgetDialog'
import { Button } from '@/components/ui/button'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
    Database,
    FileText,
    Wand2,
    TrendingUp,
    Plus,
    FileSpreadsheet,
    FileJson,
    Globe,
    Search,
    Edit3,
    Radio,
    ChevronDown
} from 'lucide-react'
import {
    WidgetNode,
    CommentNode,
    SourceNode,
    ContentNode,
    Edge,
    EdgeType,
    DataSourceType,
    SourceType
} from '@/types'
import { useBoardSocket } from '@/hooks/useBoardSocket'
import { notify } from '@/store/notificationStore'
import { findFreePosition } from '@/lib/canvasUtils'
import { contentNodesAPI } from '@/services/api'
import { findOptimalNodePosition, findNearestFreePosition, convertNodesToBounds, NodeBounds } from '@/lib/nodePositioning'

// Source types configuration
const SOURCE_TYPES = [
    { type: SourceType.CSV, label: 'CSV', icon: FileSpreadsheet, color: 'text-green-500' },
    { type: SourceType.JSON, label: 'JSON', icon: FileJson, color: 'text-yellow-500' },
    { type: SourceType.EXCEL, label: 'Excel', icon: FileSpreadsheet, color: 'text-emerald-600' },
    { type: SourceType.DOCUMENT, label: 'Документ', icon: FileText, color: 'text-blue-500' },
    { type: SourceType.API, label: 'API', icon: Globe, color: 'text-purple-500' },
    { type: SourceType.DATABASE, label: 'База данных', icon: Database, color: 'text-orange-500' },
    { type: SourceType.RESEARCH, label: 'AI Research', icon: Search, color: 'text-pink-500' },
    { type: SourceType.MANUAL, label: 'Ручной ввод', icon: Edit3, color: 'text-gray-500' },
    { type: SourceType.STREAM, label: 'Стрим', icon: Radio, color: 'text-cyan-500', disabled: true },
]

// Node types map
const nodeTypes = {
    widgetNode: WidgetNodeCard,
    commentNode: CommentNodeCard,
    sourceNode: SourceNodeCard,
    contentNode: ContentNodeCard,
}

// Edge types map
const edgeTypes = {
    transformation: TransformationEdge,
}


// Convert WidgetNode to ReactFlow Node
function widgetNodeToReactFlowNode(node: WidgetNode): Node {
    return {
        id: node.id,
        type: 'widgetNode',
        position: { x: node.x, y: node.y },
        data: { widgetNode: node },
        resizing: true,
        style: {
            width: node.width,
            height: node.height,
        },
    }
}

// Convert CommentNode to ReactFlow Node
function commentNodeToReactFlowNode(node: CommentNode): Node {
    return {
        id: node.id,
        type: 'commentNode',
        position: { x: node.x, y: node.y },
        data: { commentNode: node },
        resizing: true,
        style: {
            width: node.width || 240,
            minHeight: node.height || 120,
        },
    }
}

// Convert SourceNode to ReactFlow Node
function sourceNodeToReactFlowNode(node: SourceNode): Node {
    return {
        id: node.id,
        type: 'sourceNode',
        position: node.position,
        data: { sourceNode: node },
    }
}

// Convert ContentNode to ReactFlow Node
function contentNodeToReactFlowNode(node: ContentNode): Node {
    return {
        id: node.id,
        type: 'contentNode',
        position: node.position,
        data: { contentNode: node },
    }
}

// Get edge color based on type
function getEdgeColor(edgeType: EdgeType): string {
    switch (edgeType) {
        case EdgeType.TRANSFORMATION:
            return '#3b82f6' // blue
        case EdgeType.VISUALIZATION:
            return '#a855f7' // purple
        case EdgeType.COMMENT:
            return '#f59e0b' // amber
        case EdgeType.DRILL_DOWN:
            return '#10b981' // green
        case EdgeType.REFERENCE:
            return '#6b7280' // gray
        default:
            return '#8b5cf6'
    }
}

// Convert Edge to ReactFlow Edge
function edgeToReactFlowEdge(edge: Edge, onTransform?: (prompt: string, code?: string, transformationId?: string) => Promise<void>): ReactFlowEdge {
    const config = edge.visual_config || {}
    const color = config.color || getEdgeColor(edge.edge_type)

    const strokeDasharray =
        config.line_style === 'dashed' ? '5,5' : config.line_style === 'dotted' ? '2,4' : undefined

    const animated = config.animation === 'flow' || config.animation === 'pulse'

    // For TRANSFORMATION edges, use custom edge type with data
    if (edge.edge_type === EdgeType.TRANSFORMATION) {
        return {
            id: edge.id,
            source: edge.source_node_id,
            target: edge.target_node_id,
            type: 'transformation',
            animated,
            style: {
                stroke: color,
                strokeWidth: 2,
                strokeDasharray,
            },
            markerEnd: {
                type: 'arrowclosed',
                color,
            },
            data: {
                code: edge.transformation_params?.code,
                prompt: edge.transformation_params?.prompt || edge.label,  // Use saved prompt or fallback to label
                transformationId: edge.transformation_params?.transformation_id,
                onTransform,
            },
        }
    }

    // For VISUALIZATION edges, use vertical ports (bottom → top)
    if (edge.edge_type === EdgeType.VISUALIZATION) {
        return {
            id: edge.id,
            source: edge.source_node_id,
            target: edge.target_node_id,
            sourceHandle: 'visualize',  // Bottom port of ContentNode
            targetHandle: 'visualize',  // Top port of WidgetNode
            type: 'default',  // Smooth bezier curve
            animated,
            style: {
                stroke: color,
                strokeWidth: 2,
                strokeDasharray,
            },
            markerEnd: {
                type: 'arrowclosed',
                color,
            },
        }
    }

    return {
        id: edge.id,
        source: edge.source_node_id,
        target: edge.target_node_id,
        label: edge.label || undefined,
        type: config.arrow_type === 'bidirectional' ? 'default' : 'smoothstep',
        animated,
        style: {
            stroke: color,
            strokeWidth: 2,
            strokeDasharray,
        },
        markerEnd: {
            type: 'arrowclosed',
            color,
        },
    }
}

export function BoardCanvas() {
    const { boardId } = useParams<{ boardId: string }>()
    const reactFlowInstance = useReactFlow()
    const {
        widgetNodes,
        commentNodes,
        sourceNodes,
        contentNodes,
        edges: storeEdges,
        updateWidgetNode,
        updateCommentNode,
        updateSourceNode,
        updateContentNode,
        deleteWidgetNode,
        deleteCommentNode,
        deleteSourceNode,
        deleteContentNode,
        createEdge,
        deleteEdge,
        fetchEdges,
        fetchWidgetNodes,
        fetchCommentNodes,
        fetchSourceNodes,
        fetchContentNodes,
        createWidgetNode,
        createCommentNode,
        createSourceNode,
        clearBoardData,
    } = useBoardStore()

    const [nodes, setNodes] = useState<Node[]>([])
    const [edges, setEdges] = useState<ReactFlowEdge[]>([])

    // State for source type being dropped (for dialog)
    const [droppedSourceType, setDroppedSourceType] = useState<string | null>(null)

    // Dialogs state
    const [showSourceNodeModal, setShowSourceNodeModal] = useState(false)
    const [showTransformDialog, setShowTransformDialog] = useState(false)
    const [selectedNodesForTransform, setSelectedNodesForTransform] = useState<ContentNode[]>([])
    const [selectedSourceNodeForTransform, setSelectedSourceNodeForTransform] = useState<SourceNode | null>(null)
    const [showWidgetDialog, setShowWidgetDialog] = useState(false)
    const [selectedContentNodeForVisualize, setSelectedContentNodeForVisualize] = useState<ContentNode | null>(null)
    const [selectedSourceNodeForVisualize, setSelectedSourceNodeForVisualize] = useState<SourceNode | null>(null)
    const [newNodePosition, setNewNodePosition] = useState({ x: 100, y: 100 })

    const { setSocket } = useAIAssistantStore()

    // Connect to WebSocket for real-time collaboration
    const { socket, isConnected } = useBoardSocket(boardId)

    // Pass socket to AI Assistant store
    useEffect(() => {
        if (socket) {
            setSocket(socket)
        }
    }, [socket, setSocket])

    // Fetch all nodes and edges when board loads
    useEffect(() => {
        if (boardId) {
            // Clear previous board data before loading new board
            clearBoardData()

            // Fetch all data for the new board
            fetchWidgetNodes(boardId)
            fetchCommentNodes(boardId)
            fetchSourceNodes(boardId)
            fetchContentNodes(boardId)
            fetchEdges(boardId)
        }
    }, [boardId, clearBoardData, fetchWidgetNodes, fetchCommentNodes, fetchSourceNodes, fetchContentNodes, fetchEdges])

    // Update nodes when any node type changes
    useEffect(() => {
        console.log('🔄 BoardCanvas: Rebuilding nodes from store', {
            widgetNodes: widgetNodes.length,
            commentNodes: commentNodes.length,
            sourceNodes: sourceNodes.length,
            contentNodes: contentNodes.length,
        })

        // Exclude SourceNodes from contentNodes (they have node_type === NodeType.SOURCE_NODE)
        // Since SourceNode inherits ContentNode in DB, they come in contentNodes array
        const pureContentNodes = contentNodes.filter(node => node.node_type === 'content_node')

        const allNodes = [
            ...widgetNodes.map(widgetNodeToReactFlowNode),
            ...commentNodes.map(commentNodeToReactFlowNode),
            ...sourceNodes.map(sourceNodeToReactFlowNode),
            ...pureContentNodes.map(contentNodeToReactFlowNode),
        ]

        console.log('🎨 BoardCanvas: Final node counts', {
            widgetNodes: widgetNodes.length,
            commentNodes: commentNodes.length,
            sourceNodes: sourceNodes.length,
            pureContentNodes: pureContentNodes.length,
            total: allNodes.length,
        })

        setNodes(allNodes)
    }, [widgetNodes, commentNodes, sourceNodes, contentNodes])

    // Callback for transformation edge re-execution
    const handleTransformationEdit = useCallback(async (prompt: string, code?: string, transformationId?: string) => {
        if (!boardId) return

        try {
            // For now, we need to find which node is being transformed
            // This will be called from TransformationEdge with sourceNode context
            notify.info('Обновление трансформации...')

            // The edge should pass sourceNodeId in the callback context
            // For now, show a notification
            notify.success('Функция редактирования трансформации будет реализована')
        } catch (error) {
            notify.error('Ошибка при обновлении трансформации')
        }
    }, [boardId])

    // Handle drag over for source vitrina drop
    const onDragOver = useCallback((event: React.DragEvent) => {
        event.preventDefault()
        event.dataTransfer.dropEffect = 'copy'
    }, [])

    // Handle drop from source vitrina
    const onDrop = useCallback(
        (event: React.DragEvent) => {
            event.preventDefault()

            const dataStr = event.dataTransfer.getData('application/json')
            if (!dataStr) return

            try {
                const data = JSON.parse(dataStr)
                if (data.type !== 'source_node') return

                // Get drop position in flow coordinates
                const bounds = event.currentTarget.getBoundingClientRect()
                const position = reactFlowInstance.screenToFlowPosition({
                    x: event.clientX - bounds.left,
                    y: event.clientY - bounds.top,
                })

                // Set position and source type, then open dialog
                setNewNodePosition({ x: position.x, y: position.y })
                setDroppedSourceType(data.source_type)
                setShowSourceNodeModal(true)
            } catch (e) {
                console.error('Failed to parse drop data:', e)
            }
        },
        [reactFlowInstance]
    )

    // Update edges when store edges change
    useEffect(() => {
        const reactFlowEdges = (storeEdges || []).map((edge) => edgeToReactFlowEdge(edge, handleTransformationEdit))
        setEdges(reactFlowEdges)
    }, [storeEdges, handleTransformationEdit])

    const onNodesChange = useCallback(
        (changes: NodeChange[]) => {
            setNodes((nds) => applyNodeChanges(changes, nds))

            // Update node positions and dimensions in store
            changes.forEach((change) => {
                if (!('id' in change) || !change.id || !boardId) return

                // Find node in any of the arrays
                const widgetNode = widgetNodes.find((n) => n.id === change.id)
                const commentNode = commentNodes.find((n) => n.id === change.id)
                const sourceNode = sourceNodes.find((n) => n.id === change.id)
                const contentNode = contentNodes.find((n) => n.id === change.id)

                // Handle node removal (Delete key or context menu)
                if (change.type === 'remove') {
                    if (widgetNode) {
                        deleteWidgetNode(boardId, widgetNode.id)
                    } else if (commentNode) {
                        deleteCommentNode(boardId, commentNode.id)
                    } else if (sourceNode) {
                        deleteSourceNode(sourceNode.id)
                    } else if (contentNode) {
                        deleteContentNode(contentNode.id)
                    }
                    return
                }

                // Update position when drag ends
                if (change.type === 'position' && change.position && change.dragging === false) {
                    let x = Math.round(change.position.x)
                    let y = Math.round(change.position.y)

                    // Get current node dimensions
                    let nodeWidth = 320
                    let nodeHeight = 200
                    if (widgetNode) {
                        nodeWidth = widgetNode.width || 400
                        nodeHeight = widgetNode.height || 300
                    } else if (commentNode) {
                        nodeWidth = commentNode.width || 300
                        nodeHeight = commentNode.height || 180
                    } else if (sourceNode) {
                        nodeWidth = sourceNode.width || 280
                        nodeHeight = sourceNode.height || 150
                    } else if (contentNode) {
                        nodeWidth = contentNode.width || 320
                        nodeHeight = contentNode.height || 200
                    }

                    // Check collision with other nodes
                    const otherNodes: NodeBounds[] = []

                    widgetNodes.forEach(n => {
                        if (n.id !== change.id) {
                            otherNodes.push({
                                id: n.id,
                                x: n.x || 0,
                                y: n.y || 0,
                                width: n.width || 400,
                                height: n.height || 300
                            })
                        }
                    })

                    commentNodes.forEach(n => {
                        if (n.id !== change.id) {
                            otherNodes.push({
                                id: n.id,
                                x: n.x || 0,
                                y: n.y || 0,
                                width: n.width || 300,
                                height: n.height || 180
                            })
                        }
                    })

                    sourceNodes.forEach(n => {
                        if (n.id !== change.id) {
                            otherNodes.push({
                                id: n.id,
                                x: n.position?.x || 0,
                                y: n.position?.y || 0,
                                width: n.width || 280,
                                height: n.height || 150
                            })
                        }
                    })

                    contentNodes.forEach(n => {
                        if (n.id !== change.id) {
                            otherNodes.push({
                                id: n.id,
                                x: n.position?.x || 0,
                                y: n.position?.y || 0,
                                width: n.width || 320,
                                height: n.height || 200
                            })
                        }
                    })

                    // Use collision detection from our positioning utility
                    const checkCollision = (
                        bounds1: { x: number; y: number; width: number; height: number },
                        bounds2: { x: number; y: number; width: number; height: number },
                        padding: number = 40
                    ): boolean => {
                        return !(
                            bounds1.x + bounds1.width + padding < bounds2.x ||
                            bounds1.x > bounds2.x + bounds2.width + padding ||
                            bounds1.y + bounds1.height + padding < bounds2.y ||
                            bounds1.y > bounds2.y + bounds2.height + padding
                        )
                    }

                    const currentBounds = { x, y, width: nodeWidth, height: nodeHeight }
                    const hasCollision = otherNodes.some(node => checkCollision(currentBounds, node))

                    if (hasCollision) {
                        console.warn('⚠️ Node collision detected, finding nearest free space...')

                        // Find NEAREST free position (minimal movement)
                        const nearestFreePos = findNearestFreePosition(
                            { x, y },
                            nodeWidth,
                            nodeHeight,
                            otherNodes,
                            40 // padding
                        )

                        x = Math.round(nearestFreePos.x)
                        y = Math.round(nearestFreePos.y)

                        // Update React Flow node position immediately
                        setNodes((nds) =>
                            nds.map(n =>
                                n.id === change.id
                                    ? { ...n, position: { x, y } }
                                    : n
                            )
                        )
                    }

                    if (widgetNode) {
                        updateWidgetNode(boardId, widgetNode.id, { x, y })
                    } else if (commentNode) {
                        updateCommentNode(boardId, commentNode.id, { x, y })
                    } else if (sourceNode) {
                        updateSourceNode(sourceNode.id, { position: { x, y } })
                    } else if (contentNode) {
                        updateContentNode(contentNode.id, { position: { x, y } })
                    }
                }

                // Update dimensions when resize ends (only for WidgetNode and CommentNode)
                if (change.type === 'dimensions' && change.dimensions && change.resizing === false) {
                    const width = Math.max(100, Math.min(2000, Math.round(change.dimensions.width)))
                    const height = Math.max(100, Math.min(2000, Math.round(change.dimensions.height)))

                    if (widgetNode) {
                        updateWidgetNode(boardId, widgetNode.id, { width, height })
                    } else if (commentNode) {
                        updateCommentNode(boardId, commentNode.id, { width, height })
                    }
                }
            })
        },
        [
            widgetNodes, commentNodes, sourceNodes, contentNodes,
            boardId,
            updateWidgetNode, updateCommentNode, updateSourceNode, updateContentNode,
            deleteWidgetNode, deleteCommentNode, deleteSourceNode, deleteContentNode
        ]
    )

    const onEdgesChange = useCallback((changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)), [])

    const onConnect = useCallback(
        (connection: Connection) => {
            if (!boardId || !connection.source || !connection.target) return

            // Determine node types
            const sourceWidgetNode = widgetNodes.find((n) => n.id === connection.source)
            const sourceCommentNode = commentNodes.find((n) => n.id === connection.source)
            const sourceNode = sourceNodes.find((n) => n.id === connection.source)
            const sourceContentNode = contentNodes.find((n) => n.id === connection.source)

            const targetWidgetNode = widgetNodes.find((n) => n.id === connection.target)
            const targetCommentNode = commentNodes.find((n) => n.id === connection.target)
            const targetNode = sourceNodes.find((n) => n.id === connection.target)
            const targetContentNode = contentNodes.find((n) => n.id === connection.target)

            let sourceNodeType = 'SourceNode'
            let targetNodeType = 'ContentNode'
            let edgeType = EdgeType.REFERENCE

            if (sourceNode) sourceNodeType = 'SourceNode'
            else if (sourceContentNode) sourceNodeType = 'ContentNode'
            else if (sourceWidgetNode) sourceNodeType = 'WidgetNode'
            else if (sourceCommentNode) sourceNodeType = 'CommentNode'

            if (targetNode) targetNodeType = 'SourceNode'
            else if (targetContentNode) targetNodeType = 'ContentNode'
            else if (targetWidgetNode) targetNodeType = 'WidgetNode'
            else if (targetCommentNode) targetNodeType = 'CommentNode'

            // Auto-detect edge type (v2.0: SourceNode наследует ContentNode)
            // SourceNode/ContentNode → ContentNode = TRANSFORMATION
            // SourceNode/ContentNode → WidgetNode = VISUALIZATION
            const isContentBearingSource = sourceNodeType === 'SourceNode' || sourceNodeType === 'ContentNode'

            if (isContentBearingSource && targetNodeType === 'ContentNode') {
                edgeType = EdgeType.TRANSFORMATION
            } else if (isContentBearingSource && targetNodeType === 'WidgetNode') {
                edgeType = EdgeType.VISUALIZATION
            } else if (sourceNodeType === 'CommentNode') {
                edgeType = EdgeType.COMMENT
            }

            // Create edge in backend
            createEdge(boardId, {
                source_node_id: connection.source,
                target_node_id: connection.target,
                source_node_type: sourceNodeType,
                target_node_type: targetNodeType,
                edge_type: edgeType,
                label: edgeType,
            })
        },
        [boardId, widgetNodes, commentNodes, sourceNodes, contentNodes, createEdge]
    )

    const onPaneClick = useCallback(() => {
        // Pane clicked - can be used for deselection or other actions
    }, [])

    // Handle node and edge deletion
    const handleDeleteSelection = useCallback(async () => {
        if (!boardId) return

        // Get selected nodes and edges from local state (updated by onNodesChange/onEdgesChange)
        const selectedNodeIds = nodes.filter(node => node.selected).map(node => node.id)
        const selectedEdgeIds = edges.filter(edge => edge.selected).map(edge => edge.id)

        console.log('🗑️ Deleting:', { nodes: selectedNodeIds, edges: selectedEdgeIds })

        // Delete selected nodes
        for (const nodeId of selectedNodeIds) {
            const widgetNode = widgetNodes.find((n) => n.id === nodeId)
            const commentNode = commentNodes.find((n) => n.id === nodeId)
            const sourceNode = sourceNodes.find((n) => n.id === nodeId)
            const contentNode = contentNodes.find((n) => n.id === nodeId)

            if (widgetNode) {
                await deleteWidgetNode(boardId, nodeId)
            } else if (commentNode) {
                await deleteCommentNode(boardId, nodeId)
            } else if (sourceNode) {
                await deleteSourceNode(nodeId)
            } else if (contentNode) {
                await deleteContentNode(nodeId)
            }
        }

        // Delete selected edges
        for (const edgeId of selectedEdgeIds) {
            await deleteEdge(boardId, edgeId)
        }
    }, [boardId, nodes, edges, widgetNodes, commentNodes, sourceNodes, contentNodes, deleteWidgetNode, deleteCommentNode, deleteSourceNode, deleteContentNode, deleteEdge])

    // Listen for Delete key press
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Don't handle delete if focus is on input/textarea
            const target = e.target as HTMLElement
            if (
                target.tagName === 'INPUT' ||
                target.tagName === 'TEXTAREA' ||
                target.isContentEditable
            ) {
                return
            }

            if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault()
                handleDeleteSelection()
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [handleDeleteSelection])

    // Handle visualize for selected ContentNode or SourceNode
    const handleVisualizeSelected = useCallback(() => {
        // First check for ContentNodes
        const selectedContentNodes = nodes
            .filter((n) => n.selected && n.type === 'contentNode')
            .map((n) => contentNodes.find((cn) => cn.id === n.id))
            .filter((cn): cn is ContentNode => cn !== undefined)

        if (selectedContentNodes.length > 0) {
            // Use the first selected ContentNode
            setSelectedContentNodeForVisualize(selectedContentNodes[0])
            setSelectedSourceNodeForVisualize(null)
            setShowWidgetDialog(true)
            return
        }

        // Check for SourceNodes (which now can have content)
        const selectedSourceNodes = nodes
            .filter((n) => n.selected && n.type === 'sourceNode')
            .map((n) => sourceNodes.find((sn) => sn.id === n.id))
            .filter((sn): sn is SourceNode => sn !== undefined && !!sn.content)

        if (selectedSourceNodes.length > 0) {
            // Use the first selected SourceNode with content
            setSelectedSourceNodeForVisualize(selectedSourceNodes[0])
            setSelectedContentNodeForVisualize(null)
            setShowWidgetDialog(true)
            return
        }

        notify.warning('Выберите ContentNode или SourceNode с данными для визуализации')
    }, [nodes, contentNodes, sourceNodes])

    const handleCreateWidgetNode = useCallback(async () => {
        if (!boardId) return

        // Find free position for widget node
        const allNodes = [...widgetNodes, ...commentNodes, ...sourceNodes, ...contentNodes]
        const { x, y } = findFreePosition(allNodes, 300, 100, 'widgetNode')

        await createWidgetNode(boardId, {
            name: 'New WidgetNode',
            description: 'Новая визуализация',
            html_code: '<div style="padding: 20px; text-align: center;"><h2>Sample Widget</h2><p>Визуализация данных</p></div>',
            css_code: '',
            js_code: '',
            x,
            y,
            width: 400,
            height: 300,
        })
    }, [boardId, widgetNodes, commentNodes, sourceNodes, contentNodes, createWidgetNode])

    const handleCreateCommentNode = useCallback(async () => {
        if (!boardId) return

        // Find free position for comment node
        const allNodes = [...widgetNodes, ...commentNodes, ...sourceNodes, ...contentNodes]
        const { x, y } = findFreePosition(allNodes, 500, 100, 'commentNode')

        await createCommentNode(boardId, {
            content: 'Новый комментарий',
            x,
            y,
            width: 240,
            height: 120,
        })
    }, [boardId, widgetNodes, commentNodes, sourceNodes, contentNodes, createCommentNode])

    // Handle create SourceNode
    const handleCreateSourceNode = useCallback((sourceType?: string) => {
        // Calculate free position
        const allNodes = [...widgetNodes, ...commentNodes, ...sourceNodes, ...contentNodes]
        const position = findFreePosition(allNodes, 300, 100, 'sourceNode')
        setNewNodePosition(position)
        setDroppedSourceType(sourceType || null)
        setShowSourceNodeModal(true)
    }, [widgetNodes, commentNodes, sourceNodes, contentNodes])

    // Handle transform selected ContentNodes or SourceNode
    const handleTransformSelected = useCallback(() => {
        // First check for ContentNodes
        const selectedContentNodeIds = nodes.filter((n) => n.selected && n.type === 'contentNode')

        if (selectedContentNodeIds.length > 0) {
            // Get actual ContentNode objects from store
            const contentNodesForTransform = contentNodes.filter(cn =>
                selectedContentNodeIds.some(n => n.id === cn.id)
            )

            setSelectedNodesForTransform(contentNodesForTransform)
            setSelectedSourceNodeForTransform(null)

            // Calculate position near selected nodes
            const avgX = selectedContentNodeIds.reduce((sum, n) => sum + (n.position?.x || 0), 0) / selectedContentNodeIds.length
            const avgY = selectedContentNodeIds.reduce((sum, n) => sum + (n.position?.y || 0), 0) / selectedContentNodeIds.length
            setNewNodePosition({ x: avgX + 300, y: avgY })

            setShowTransformDialog(true)
            return
        }

        // Check for SourceNodes with content
        const selectedSourceNodeIds = nodes.filter((n) => n.selected && n.type === 'sourceNode')

        if (selectedSourceNodeIds.length > 0) {
            const sourceNodeForTransform = sourceNodes.find(sn =>
                sn.id === selectedSourceNodeIds[0].id && !!sn.content
            )

            if (sourceNodeForTransform) {
                setSelectedSourceNodeForTransform(sourceNodeForTransform)
                setSelectedNodesForTransform([])

                const node = selectedSourceNodeIds[0]
                setNewNodePosition({ x: (node.position?.x || 0) + 300, y: node.position?.y || 0 })

                setShowTransformDialog(true)
                return
            }
        }

        notify.error('Выберите ContentNode или SourceNode с данными для трансформации')
    }, [nodes, contentNodes, sourceNodes])

    // Handle drag & drop for files
    const handleDragEnter = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()

        if (e.dataTransfer.types.includes('Files')) {
            setDragDepth((prev) => prev + 1)
            setIsDraggingFile(true)
        }
    }, [])

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
    }, [])

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()

        setDragDepth((prev) => {
            const newDepth = prev - 1
            if (newDepth === 0) {
                setIsDraggingFile(false)
            }
            return newDepth
        })
    }, [])

    const totalNodes = widgetNodes.length + commentNodes.length + sourceNodes.length + contentNodes.length
    const hasSelectedContentNodes = nodes.some((n) => n.selected && n.type === 'contentNode')

    // Check if selected SourceNode has content (for transform/visualize)
    const selectedSourceNodeWithContent = nodes
        .filter((n) => n.selected && n.type === 'sourceNode')
        .map((n) => sourceNodes.find((sn) => sn.id === n.id))
        .find((sn) => sn?.content)
    const hasSelectedSourceNodeWithContent = !!selectedSourceNodeWithContent

    // Can show transform/visualize buttons for ContentNodes OR SourceNodes with content
    const canTransformOrVisualize = hasSelectedContentNodes || hasSelectedSourceNodeWithContent

    return (
        <div className="relative w-full h-full">
            {/* Quick Create Toolbar */}
            <div className="absolute top-4 left-4 z-10 flex gap-2">
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button
                            size="sm"
                            variant="outline"
                            className="shadow-md"
                        >
                            <Plus className="mr-2 h-4 w-4" />
                            Добавить источник
                            <ChevronDown className="ml-2 h-3 w-3 opacity-50" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-56">
                        {SOURCE_TYPES.map((source) => {
                            const Icon = source.icon
                            return (
                                <DropdownMenuItem
                                    key={source.type}
                                    onClick={() => handleCreateSourceNode(source.type)}
                                    disabled={source.disabled}
                                    className="cursor-pointer"
                                >
                                    <Icon className={`mr-2 h-4 w-4 ${source.color}`} />
                                    <span>{source.label}</span>
                                    {source.disabled && (
                                        <span className="ml-auto text-xs text-muted-foreground">скоро</span>
                                    )}
                                </DropdownMenuItem>
                            )
                        })}
                    </DropdownMenuContent>
                </DropdownMenu>

                {canTransformOrVisualize && (
                    <>
                        <Button
                            size="sm"
                            variant="outline"
                            onClick={handleTransformSelected}
                            className="shadow-md bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/20"
                        >
                            <Wand2 className="mr-2 h-4 w-4" />
                            Трансформация
                        </Button>
                        <Button
                            size="sm"
                            variant="outline"
                            onClick={handleVisualizeSelected}
                            className="shadow-md bg-purple-500/10 border-purple-500/30 hover:bg-purple-500/20"
                        >
                            <TrendingUp className="mr-2 h-4 w-4" />
                            Визуализация
                        </Button>
                    </>
                )}
            </div>

            {/* React Flow Canvas */}
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onPaneClick={onPaneClick}
                onDrop={onDrop}
                onDragOver={onDragOver}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                minZoom={0.5}
                maxZoom={2}
                defaultZoom={1}
                className="bg-muted/30"
                selectNodesOnDrag={false}
                panOnDrag={true}
                selectionOnDrag={false}
                selectionMode={SelectionMode.Partial}
                onlyRenderVisibleElements={false}
                selectionKeyCode="Shift"
                connectionMode="loose"
                connectOnClick={false}
                proOptions={{ hideAttribution: true }}
            >
                <Background gap={20} size={1} />
                <Controls />
                <MiniMap nodeStrokeWidth={3} className="bg-background border border-border" />
            </ReactFlow>

            {/* Empty state */}
            {totalNodes === 0 && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="text-center">
                        <p className="text-lg font-medium text-muted-foreground mb-2">Доска пуста</p>
                        <p className="text-sm text-muted-foreground">
                            Добавьте узлы для работы с данными и визуализацией
                        </p>
                    </div>
                </div>
            )}

            {/* Help text */}
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-xs text-muted-foreground/80 bg-background/40 backdrop-blur px-3 py-2 rounded-md border border-border/30 pointer-events-none text-center">
                <p>️ Нажмите <kbd className="px-2 py-1 bg-muted rounded font-mono">Delete</kbd> для удаления</p>
                <p>✨ Выберите ContentNodes и нажмите Transform для объединения данных</p>
            </div>

            {/* Dialogs */}
            <SourceDialogRouter
                sourceType={droppedSourceType}
                open={showSourceNodeModal}
                onOpenChange={(open) => {
                    setShowSourceNodeModal(open)
                    if (!open) setDroppedSourceType(null)
                }}
                initialPosition={newNodePosition}
            />
            {(selectedNodesForTransform.length > 0 || selectedSourceNodeForTransform) && (
                <TransformDialog
                    open={showTransformDialog}
                    onOpenChange={(open) => {
                        setShowTransformDialog(open)
                        if (!open) {
                            setSelectedNodesForTransform([])
                            setSelectedSourceNodeForTransform(null)
                        }
                    }}
                    sourceNodes={selectedNodesForTransform}
                    sourceNode={selectedSourceNodeForTransform as any}
                    onTransform={async (code, transformationId, description) => {
                        if (!boardId) return

                        console.log('🚀 onTransform called:', { code: code?.substring(0, 100), transformationId, description })

                        try {
                            // Use ContentNode or SourceNode as source
                            const sourceNodeId = selectedNodesForTransform.length > 0
                                ? selectedNodesForTransform[0].id
                                : selectedSourceNodeForTransform?.id

                            if (!sourceNodeId) {
                                throw new Error('No source node selected')
                            }

                            console.log('📤 Calling transformExecute:', { boardId, sourceNodeId, transformationId })

                            // Execute transformation with provided code
                            const result = await contentNodesAPI.transformExecute(
                                boardId,
                                sourceNodeId,
                                {
                                    code: code || '',
                                    transformation_id: transformationId,
                                    description: description || '',
                                    prompt: description || '',  // Save for editing later
                                    selected_node_ids: selectedNodesForTransform.length > 0
                                        ? selectedNodesForTransform.map(n => n.id)
                                        : [sourceNodeId]
                                }
                            )

                            console.log('✅ transformExecute result:', result)
                            notify.success('Трансформация выполнена успешно')
                            setShowTransformDialog(false)

                            // Refresh content nodes and edges to show the new node
                            await fetchContentNodes(boardId)
                            await fetchEdges(boardId)
                        } catch (error) {
                            console.error('Transformation failed:', error)
                            notify.error('Ошибка выполнения трансформации')
                            throw error // Re-throw to let dialog handle it
                        }
                    }}
                />
            )}

            {(selectedContentNodeForVisualize || selectedSourceNodeForVisualize) && (
                <WidgetDialog
                    open={showWidgetDialog}
                    onOpenChange={(open) => {
                        setShowWidgetDialog(open)
                        if (!open) {
                            setSelectedContentNodeForVisualize(null)
                            setSelectedSourceNodeForVisualize(null)
                        }
                    }}
                    contentNode={(selectedContentNodeForVisualize || selectedSourceNodeForVisualize) as any}
                    onVisualize={async (params) => {
                        const nodeToVisualize = selectedContentNodeForVisualize || selectedSourceNodeForVisualize
                        if (!nodeToVisualize) return
                        const visualizeContent = useBoardStore.getState().visualizeContent
                        await visualizeContent(nodeToVisualize.id, params)
                        setShowWidgetDialog(false)
                    }}
                    onWidgetCreated={async () => {
                        await fetchWidgetNodes(boardId)
                        await fetchEdges(boardId)
                    }}
                />
            )}
        </div>
    )
}
