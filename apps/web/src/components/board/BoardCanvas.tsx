import { useCallback, useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
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
    useStore,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useBoardStore } from '@/store/boardStore'
import { useLibraryStore } from '@/store/libraryStore'
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
    ChevronDown,
    Camera,
    Grid3X3,
    Magnet,
    Ruler,
} from 'lucide-react'
import {
    WidgetNode,
    CommentNode,
    SourceNode,
    ContentNode,
    Edge,
    EdgeType,
    SourceType
} from '@/types'
import { useBoardSocket } from '@/hooks/useBoardSocket'
import { notify } from '@/store/notificationStore'
import { findFreePosition } from '@/lib/canvasUtils'
import { contentNodesAPI, filesAPI, getFileImageUrl } from '@/services/api'
import { domToBlob } from 'modern-screenshot'
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

// Grid & smart guides (aligned with dashboard)
const GRID_SIZE = 20
const SNAP_THRESHOLD = 6

type GuideLine = { axis: 'x' | 'y'; position: number; start: number; end: number }

function snapValueToGrid(val: number, gridSize: number = GRID_SIZE): number {
    return Math.round(val / gridSize) * gridSize
}

function getDefaultSizeByNodeType(type?: string): { width: number; height: number } {
    switch (type) {
        case 'widgetNode':
            return { width: 400, height: 300 }
        case 'commentNode':
            return { width: 240, height: 120 }
        case 'sourceNode':
            return { width: 320, height: 200 }
        case 'contentNode':
            return { width: 320, height: 200 }
        default:
            return { width: 320, height: 200 }
    }
}

function getNodeRenderedSize(
    node: Node | undefined,
    fallback: { width: number; height: number }
): { width: number; height: number } {
    if (!node) return fallback

    const measured = (node as Node & { measured?: { width?: number; height?: number } }).measured
    const styleWidth = typeof node.style?.width === 'number' ? node.style.width : undefined
    const styleHeight = typeof node.style?.height === 'number' ? node.style.height : undefined

    const width = node.width ?? measured?.width ?? styleWidth ?? fallback.width
    const height = node.height ?? measured?.height ?? styleHeight ?? fallback.height

    return {
        width: Math.max(1, Math.round(width)),
        height: Math.max(1, Math.round(height)),
    }
}

/** Build bounds for all nodes except excludeId from React Flow nodes (position + style). */
function getOtherNodesBounds(
    nodes: Node[],
    excludeId: string
): NodeBounds[] {
    return nodes
        .filter((n) => n.id !== excludeId)
        .map((n) => {
            const fallback = getDefaultSizeByNodeType(n.type)
            const { width, height } = getNodeRenderedSize(n, fallback)
            return {
                id: n.id,
                x: n.position.x,
                y: n.position.y,
                width,
                height,
            }
        })
}

/** Smart guide snap: returns snapped { x, y } and guide lines to draw (dashboard logic). */
function computeSmartGuideSnap(
    movingRect: { x: number; y: number; width: number; height: number },
    otherBounds: NodeBounds[],
    threshold: number = SNAP_THRESHOLD
): { x: number; y: number; guides: GuideLine[] } {
    const guides: GuideLine[] = []
    let snapDx = 0
    let snapDy = 0
    let snappedX = false
    let snappedY = false

    const movingEdges = {
        left: movingRect.x,
        right: movingRect.x + movingRect.width,
        centerX: movingRect.x + movingRect.width / 2,
        top: movingRect.y,
        bottom: movingRect.y + movingRect.height,
        centerY: movingRect.y + movingRect.height / 2,
    }

    for (const other of otherBounds) {
        const otherEdges = {
            left: other.x,
            right: other.x + other.width,
            centerX: other.x + other.width / 2,
            top: other.y,
            bottom: other.y + other.height,
            centerY: other.y + other.height / 2,
        }

        if (!snappedX) {
            const xPairs: [number, number][] = [
                [movingEdges.left, otherEdges.left],
                [movingEdges.left, otherEdges.right],
                [movingEdges.right, otherEdges.left],
                [movingEdges.right, otherEdges.right],
                [movingEdges.centerX, otherEdges.centerX],
            ]
            for (const [mv, ov] of xPairs) {
                if (Math.abs(mv - ov) < threshold) {
                    snapDx = ov - mv
                    snappedX = true
                    break
                }
            }
        }
        if (!snappedY) {
            const yPairs: [number, number][] = [
                [movingEdges.top, otherEdges.top],
                [movingEdges.top, otherEdges.bottom],
                [movingEdges.bottom, otherEdges.top],
                [movingEdges.bottom, otherEdges.bottom],
                [movingEdges.centerY, otherEdges.centerY],
            ]
            for (const [mv, ov] of yPairs) {
                if (Math.abs(mv - ov) < threshold) {
                    snapDy = ov - mv
                    snappedY = true
                    break
                }
            }
        }
    }

    const correctedX = movingRect.x + snapDx
    const correctedY = movingRect.y + snapDy
    const correctedRect = { x: correctedX, y: correctedY, width: movingRect.width, height: movingRect.height }
    const finalEdges = {
        left: correctedRect.x,
        right: correctedRect.x + correctedRect.width,
        centerX: correctedRect.x + correctedRect.width / 2,
        top: correctedRect.y,
        bottom: correctedRect.y + correctedRect.height,
        centerY: correctedRect.y + correctedRect.height / 2,
    }

    for (const other of otherBounds) {
        const otherEdges = {
            left: other.x,
            right: other.x + other.width,
            centerX: other.x + other.width / 2,
            top: other.y,
            bottom: other.y + other.height,
            centerY: other.y + other.height / 2,
        }
        const xMatches: [number, number][] = [
            [finalEdges.left, otherEdges.left],
            [finalEdges.left, otherEdges.right],
            [finalEdges.right, otherEdges.left],
            [finalEdges.right, otherEdges.right],
            [finalEdges.centerX, otherEdges.centerX],
        ]
        for (const [mv, ov] of xMatches) {
            if (Math.abs(mv - ov) < 1) {
                const minY = Math.min(correctedRect.y, other.y) - 10
                const maxY = Math.max(correctedRect.y + correctedRect.height, other.y + other.height) + 10
                guides.push({ axis: 'x', position: ov, start: minY, end: maxY })
            }
        }
        const yMatches: [number, number][] = [
            [finalEdges.top, otherEdges.top],
            [finalEdges.top, otherEdges.bottom],
            [finalEdges.bottom, otherEdges.top],
            [finalEdges.bottom, otherEdges.bottom],
            [finalEdges.centerY, otherEdges.centerY],
        ]
        for (const [mv, ov] of yMatches) {
            if (Math.abs(mv - ov) < 1) {
                const minX = Math.min(correctedRect.x, other.x) - 10
                const maxX = Math.max(correctedRect.x + correctedRect.width, other.x + other.width) + 10
                guides.push({ axis: 'y', position: ov, start: minX, end: maxX })
            }
        }
    }

    return { x: correctedX, y: correctedY, guides }
}

/** При ресайзе: привязка правого и нижнего краёв к краям других нод (умные направляющие). */
function computeResizeSmartGuideSnap(
    x: number,
    y: number,
    width: number,
    height: number,
    otherBounds: NodeBounds[],
    threshold: number = SNAP_THRESHOLD
): { width: number; height: number } {
    let newWidth = width
    let newHeight = height
    const right = x + width
    const bottom = y + height

    for (const other of otherBounds) {
        const oLeft = other.x
        const oRight = other.x + other.width
        const oTop = other.y
        const oBottom = other.y + other.height

        if (Math.abs(right - oLeft) < threshold) newWidth = oLeft - x
        else if (Math.abs(right - oRight) < threshold) newWidth = oRight - x
        if (Math.abs(bottom - oTop) < threshold) newHeight = oTop - y
        else if (Math.abs(bottom - oBottom) < threshold) newHeight = oBottom - y
    }

    return {
        width: Math.max(100, Math.min(2000, Math.round(newWidth))),
        height: Math.max(100, Math.min(2000, Math.round(newHeight))),
    }
}

/** Строит линии направляющих для прямоугольника (для отображения при ресайзе). */
function getGuidesForRect(
    rect: { x: number; y: number; width: number; height: number },
    otherBounds: NodeBounds[]
): GuideLine[] {
    const guides: GuideLine[] = []
    const edges = {
        left: rect.x,
        right: rect.x + rect.width,
        centerX: rect.x + rect.width / 2,
        top: rect.y,
        bottom: rect.y + rect.height,
        centerY: rect.y + rect.height / 2,
    }
    for (const other of otherBounds) {
        const o = {
            left: other.x,
            right: other.x + other.width,
            centerX: other.x + other.width / 2,
            top: other.y,
            bottom: other.y + other.height,
            centerY: other.y + other.height / 2,
        }
        const xPairs: [number, number][] = [
            [edges.left, o.left], [edges.left, o.right], [edges.right, o.left], [edges.right, o.right], [edges.centerX, o.centerX],
        ]
        for (const [mv, ov] of xPairs) {
            if (Math.abs(mv - ov) < 1) {
                const minY = Math.min(rect.y, other.y) - 10
                const maxY = Math.max(rect.y + rect.height, other.y + other.height) + 10
                guides.push({ axis: 'x', position: ov, start: minY, end: maxY })
            }
        }
        const yPairs: [number, number][] = [
            [edges.top, o.top], [edges.top, o.bottom], [edges.bottom, o.top], [edges.bottom, o.bottom], [edges.centerY, o.centerY],
        ]
        for (const [mv, ov] of yPairs) {
            if (Math.abs(mv - ov) < 1) {
                const minX = Math.min(rect.x, other.x) - 10
                const maxX = Math.max(rect.x + rect.width, other.x + other.width) + 10
                guides.push({ axis: 'y', position: ov, start: minX, end: maxX })
            }
        }
    }
    return guides
}

const DIAMOND = 3

/** flow → пиксели в системе контейнера: viewport transform [tx, ty, zoom]. */
function flowToContainer(flow: { x: number; y: number }, [tx, ty, zoom]: [number, number, number]) {
    return { x: flow.x * zoom + tx, y: flow.y * zoom + ty }
}

/** Оверлей направляющих в пикселях контейнера. Рисует поверх канваса. */
function GuideLinesOverlayPixels({
    guideLines,
    transform,
}: {
    guideLines: GuideLine[]
    transform: [number, number, number]
}) {
    const [tx, ty, zoom] = transform
    return (
        <div
            className="absolute inset-0 pointer-events-none"
            style={{ zIndex: 9999 }}
        >
            {guideLines.map((g, i) => {
                if (g.axis === 'x') {
                    const pStart = flowToContainer({ x: g.position, y: g.start }, transform)
                    const pEnd = flowToContainer({ x: g.position, y: g.end }, transform)
                    const left = pStart.x - DIAMOND
                    const top = Math.min(pStart.y, pEnd.y)
                    const height = Math.abs(pEnd.y - pStart.y)
                    return (
                        <div key={`g-${i}`} className="absolute" style={{ left, top, width: DIAMOND * 2 + 1, height }}>
                            <div
                                className="absolute rounded-sm"
                                style={{ left: DIAMOND, top: 0, width: 0, height: '100%', borderLeft: '2px dashed #e846e8' }}
                            />
                            <div
                                className="absolute bg-[#e846e8] rounded-sm rotate-45 opacity-95"
                                style={{ left: 0, top: -DIAMOND, width: DIAMOND * 2 + 1, height: DIAMOND * 2 + 1 }}
                            />
                            <div
                                className="absolute bg-[#e846e8] rounded-sm rotate-45 opacity-95"
                                style={{ left: 0, bottom: -DIAMOND, width: DIAMOND * 2 + 1, height: DIAMOND * 2 + 1 }}
                            />
                        </div>
                    )
                }
                const pStart = flowToContainer({ x: g.start, y: g.position }, transform)
                const pEnd = flowToContainer({ x: g.end, y: g.position }, transform)
                const left = Math.min(pStart.x, pEnd.x)
                const top = pStart.y - DIAMOND
                const width = Math.abs(pEnd.x - pStart.x)
                return (
                    <div key={`g-${i}`} className="absolute" style={{ left, top, width, height: DIAMOND * 2 + 1 }}>
                        <div
                            className="absolute rounded-sm"
                            style={{ left: 0, top: DIAMOND, width: '100%', height: 0, borderTop: '2px dashed #e846e8' }}
                        />
                        <div
                            className="absolute bg-[#e846e8] rounded-sm rotate-45 opacity-95"
                            style={{ left: -DIAMOND, top: 0, width: DIAMOND * 2 + 1, height: DIAMOND * 2 + 1 }}
                        />
                        <div
                            className="absolute bg-[#e846e8] rounded-sm rotate-45 opacity-95"
                            style={{ right: -DIAMOND, top: 0, width: DIAMOND * 2 + 1, height: DIAMOND * 2 + 1 }}
                        />
                    </div>
                )
            })}
        </div>
    )
}

/**
 * Мост: внутри ReactFlow есть доступ к store. Рендерим оверлей через createPortal
 * в контейнер доски и рисуем направляющие в пикселях по transform из store.
 */
function GuideLinesBridge({
    guideLines,
    containerRef,
}: {
    guideLines: GuideLine[]
    containerRef: React.RefObject<HTMLDivElement | null>
}) {
    const transform = useStore((s) => s.transform) as [number, number, number]
    if (guideLines.length === 0 || !containerRef.current) return null
    return createPortal(
        <GuideLinesOverlayPixels guideLines={guideLines} transform={transform} />,
        containerRef.current
    )
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
        currentBoard,
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
        updateBoard,
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
    const [guideLines, setGuideLines] = useState<GuideLine[]>([])
    const [showGrid, setShowGrid] = useState(true)
    const [snapToGrid, setSnapToGrid] = useState(false)
    const [smartGuides, setSmartGuides] = useState(true)
    const flowContainerRef = useRef<HTMLDivElement>(null)
    const thumbnailCaptureScheduled = useRef(false)
    const initialLoadDone = useRef(false)
    const [isCapturingThumbnail, setIsCapturingThumbnail] = useState(false)

    const { setSocket, setSelectedNodes } = useAIAssistantStore()

    // Connect to WebSocket for real-time collaboration
    const { socket, isConnected } = useBoardSocket(boardId)

    // Pass socket to AI Assistant store
    useEffect(() => {
        if (socket) {
            setSocket(socket)
        }
    }, [socket, setSocket])

    // Keep selected nodes in sync with AI Assistant context.
    useEffect(() => {
        const selectedIds = nodes.filter((n) => n.selected).map((n) => n.id)
        setSelectedNodes(selectedIds)
    }, [nodes, setSelectedNodes])

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

    /** Capture canvas as image, upload, set as board thumbnail (for project overview cards). */
    const captureThumbnail = useCallback(async (silent = false) => {
        const el = flowContainerRef.current
        if (!el || !currentBoard?.id) {
            if (!silent) notify.error('Канвас ещё не готов. Подождите загрузки.', { title: 'Превью' })
            return
        }
        if (!silent) setIsCapturingThumbnail(true)
        try {
            const scale = Math.min(2, 800 / (el.offsetWidth || 1))
            const blob = await domToBlob(el, {
                scale,
                type: 'image/png',
                quality: 0.85,
                backgroundColor: 'hsl(var(--background))',
            })
            if (!blob) throw new Error('Не удалось создать изображение')
            const file = new File([blob], `board-${currentBoard.id}.png`, { type: 'image/png' })
            const { data } = await filesAPI.upload(file)
            const thumbnailUrl = getFileImageUrl(data.file_id)
            await updateBoard(currentBoard.id, { thumbnail_url: thumbnailUrl }, true)
        } catch (e) {
            console.error('Board thumbnail capture failed:', e)
            if (!silent) {
                const msg = e instanceof Error ? e.message : 'Не удалось создать превью'
                notify.error(msg, { title: 'Ошибка превью' })
            }
        } finally {
            if (!silent) setIsCapturingThumbnail(false)
        }
    }, [currentBoard, updateBoard])

    // Auto-update board thumbnail when nodes/edges change (debounced 3s, skip initial load)
    const totalNodesCount = widgetNodes.length + commentNodes.length + sourceNodes.length + contentNodes.filter(n => n.node_type === 'content_node').length
    const edgesLength = (storeEdges ?? []).length
    useEffect(() => {
        if (!boardId || totalNodesCount === 0) return
        if (!initialLoadDone.current) {
            initialLoadDone.current = true
            return
        }
        if (thumbnailCaptureScheduled.current) return
        thumbnailCaptureScheduled.current = true
        const t = window.setTimeout(async () => {
            thumbnailCaptureScheduled.current = false
            const el = flowContainerRef.current
            const board = useBoardStore.getState().currentBoard
            const update = useBoardStore.getState().updateBoard
            if (!el || !board?.id) return
            try {
                const scale = Math.min(2, 800 / (el.offsetWidth || 1))
                const blob = await domToBlob(el, {
                    scale,
                    type: 'image/png',
                    quality: 0.85,
                    backgroundColor: 'hsl(var(--background))',
                })
                if (!blob) return
                const file = new File([blob], `board-${board.id}.png`, { type: 'image/png' })
                const { data } = await filesAPI.upload(file)
                const thumbnailUrl = getFileImageUrl(data.file_id)
                await update(board.id, { thumbnail_url: thumbnailUrl }, true)
            } catch (e) {
                console.error('Board thumbnail auto-capture failed:', e)
            }
        }, 3000)
        return () => window.clearTimeout(t)
    }, [boardId, totalNodesCount, edgesLength])

    const onNodesChange = useCallback(
        (changes: NodeChange[]) => {
            // Прилипание к сетке и умным направляющим: позиция (перетаскивание) и размеры (ресайз виджета/комментария)
            const modifiedChanges: NodeChange[] = changes.map((change) => {
                // Ресайз: привязка к сетке и к умным направляющим (края к краям других нод)
                if (change.type === 'dimensions' && change.dimensions && 'id' in change && change.id) {
                    const w = change.dimensions.width ?? 0
                    const h = change.dimensions.height ?? 0
                    let width = snapToGrid ? snapValueToGrid(w) : Math.round(w)
                    let height = snapToGrid ? snapValueToGrid(h) : Math.round(h)
                    width = Math.max(100, Math.min(2000, width))
                    height = Math.max(100, Math.min(2000, height))

                    if (smartGuides) {
                        const node = nodes.find((n) => n.id === change.id)
                        if (node) {
                            const px = node.position?.x ?? 0
                            const py = node.position?.y ?? 0
                            const otherBounds = getOtherNodesBounds(nodes, change.id)
                            const guideSnapped = computeResizeSmartGuideSnap(px, py, width, height, otherBounds)
                            width = guideSnapped.width
                            height = guideSnapped.height
                        }
                    }

                    // setAttributes: true — чтобы React Flow применил наши размеры к ноде (иначе прилипание не отображается)
                    return {
                        ...change,
                        dimensions: { ...change.dimensions, width, height },
                        setAttributes: true,
                    } as NodeChange
                }
                if (change.type !== 'position' || !change.position || !('id' in change) || !change.id) {
                    return change
                }
                let x = snapToGrid ? snapValueToGrid(change.position.x) : Math.round(change.position.x)
                let y = snapToGrid ? snapValueToGrid(change.position.y) : Math.round(change.position.y)

                const movingNode = nodes.find((n) => n.id === change.id)
                const fallback = getDefaultSizeByNodeType(movingNode?.type)
                const { width: nodeWidth, height: nodeHeight } = getNodeRenderedSize(movingNode, fallback)

                if (smartGuides) {
                    const effectiveNodes = nodes.map((n) =>
                        n.id === change.id ? { ...n, position: { x, y } } : n
                    )
                    const otherBounds = getOtherNodesBounds(effectiveNodes, change.id)
                    const guideSnapped = computeSmartGuideSnap(
                        { x, y, width: nodeWidth, height: nodeHeight },
                        otherBounds
                    )
                    x = Math.round(guideSnapped.x)
                    y = Math.round(guideSnapped.y)
                }

                return { ...change, position: { x, y } }
            })

            // Умные направляющие: сбрасывать при окончании перетаскивания или ресайза; показывать только во время ресайза
            const dragEnd = changes.some((c) => c.type === 'position' && 'dragging' in c && c.dragging === false)
            const resizeEnd = changes.some((c) => c.type === 'dimensions' && 'resizing' in c && c.resizing === false)
            if (dragEnd || resizeEnd) {
                setGuideLines([])
            } else {
                // Показывать направляющие при ресайзе только когда ресайз реально идёт (resizing === true), не при любом dimension change
                const dimChangeResizing = changes.find((c): c is typeof c & { type: 'dimensions'; id: string; resizing?: boolean } => c.type === 'dimensions' && 'id' in c && !!c.id)
                if (dimChangeResizing && smartGuides && dimChangeResizing.resizing === true) {
                    const mod = modifiedChanges.find((c) => 'id' in c && c.id === dimChangeResizing.id && c.type === 'dimensions' && c.dimensions)
                    const dims = mod?.type === 'dimensions' && mod.dimensions ? mod.dimensions : dimChangeResizing.dimensions
                    if (dims) {
                        const node = nodes.find((n) => n.id === dimChangeResizing.id)
                        if (node) {
                            const px = node.position?.x ?? 0
                            const py = node.position?.y ?? 0
                            const rect = { x: px, y: py, width: dims.width, height: dims.height }
                            const otherBounds = getOtherNodesBounds(nodes, dimChangeResizing.id)
                            const guides = getGuidesForRect(rect, otherBounds)
                            setGuideLines(guides)
                        }
                    }
                }
            }

            setNodes((nds) => applyNodeChanges(modifiedChanges, nds))

            // Update store and handle remove/dimensions
            changes.forEach((change) => {
                if (!('id' in change) || !change.id || !boardId) return

                const widgetNode = widgetNodes.find((n) => n.id === change.id)
                const commentNode = commentNodes.find((n) => n.id === change.id)
                const sourceNode = sourceNodes.find((n) => n.id === change.id)
                const contentNode = contentNodes.find((n) => n.id === change.id)

                if (change.type === 'remove') {
                    if (widgetNode) deleteWidgetNode(boardId, widgetNode.id)
                    else if (commentNode) deleteCommentNode(boardId, commentNode.id)
                    else if (sourceNode) deleteSourceNode(sourceNode.id)
                    else if (contentNode) deleteContentNode(contentNode.id)
                    return
                }

                if (change.type === 'position' && change.position && change.dragging === false) {
                    const mod = modifiedChanges.find((c) => 'id' in c && c.id === change.id)
                    const pos = (mod && mod.type === 'position' && mod.position) ? mod.position : change.position
                    let x = Math.round(pos.x)
                    let y = Math.round(pos.y)

                    const movingNode = nodes.find((n) => n.id === change.id)
                    const fallback = getDefaultSizeByNodeType(movingNode?.type)
                    const { width: nodeWidth, height: nodeHeight } = getNodeRenderedSize(movingNode, fallback)
                    const effectiveNodes = nodes.map((n) =>
                        n.id === change.id ? { ...n, position: { x, y } } : n
                    )
                    const otherNodes = getOtherNodesBounds(effectiveNodes, change.id)

                    const checkCollision = (a: { x: number; y: number; width: number; height: number }, b: NodeBounds, pad = 40) =>
                        !(a.x + a.width + pad < b.x || a.x > b.x + b.width + pad || a.y + a.height + pad < b.y || a.y > b.y + b.height + pad)
                    const currentBounds = { x, y, width: nodeWidth, height: nodeHeight }
                    const hasCollision = otherNodes.some((node) => checkCollision(currentBounds, node))

                    if (hasCollision) {
                        const nearestFreePos = findNearestFreePosition({ x, y }, nodeWidth, nodeHeight, otherNodes, 40)
                        x = Math.round(nearestFreePos.x)
                        y = Math.round(nearestFreePos.y)
                        setNodes((nds) =>
                            nds.map((n) => (n.id === change.id ? { ...n, position: { x, y } } : n))
                        )
                    }

                    if (widgetNode) updateWidgetNode(boardId, widgetNode.id, { x, y })
                    else if (commentNode) updateCommentNode(boardId, commentNode.id, { x, y })
                    else if (sourceNode) updateSourceNode(sourceNode.id, { position: { x, y } })
                    else if (contentNode) updateContentNode(contentNode.id, { position: { x, y } })
                }

                // Update dimensions when resize ends (only for WidgetNode and CommentNode); используем уже привязанные к сетке значения из modifiedChanges
                if (change.type === 'dimensions' && change.dimensions && change.resizing === false) {
                    const mod = modifiedChanges.find((c) => 'id' in c && c.id === change.id && c.type === 'dimensions' && c.dimensions)
                    const dims = mod?.type === 'dimensions' && mod.dimensions ? mod.dimensions : change.dimensions
                    const width = Math.max(100, Math.min(2000, Math.round(dims.width)))
                    const height = Math.max(100, Math.min(2000, Math.round(dims.height)))

                    if (widgetNode) {
                        updateWidgetNode(boardId, widgetNode.id, { width, height })
                    } else if (commentNode) {
                        updateCommentNode(boardId, commentNode.id, { width, height })
                    }
                }
            })
        },
        [
            nodes,
            snapToGrid,
            smartGuides,
            widgetNodes, commentNodes, sourceNodes, contentNodes,
            boardId,
            updateWidgetNode, updateCommentNode, updateSourceNode, updateContentNode,
            deleteWidgetNode, deleteCommentNode, deleteSourceNode, deleteContentNode,
            setGuideLines,
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

    const onNodeDrag = useCallback(
        (_: React.MouseEvent, node: Node, _draggedNodes: Node[]) => {
            if (!smartGuides) {
                setGuideLines([])
                return
            }
            // React Flow передаёт в onNodeDrag только перетаскиваемые узлы. Для умных направляющих
            // нужны ВСЕ узлы канваса — берём из локального state, подставляя текущую позицию перетаскиваемого.
            const allNodesWithDragPosition = nodes.map((n) =>
                n.id === node.id ? { ...n, position: node.position } : n
            )
            const fallback = getDefaultSizeByNodeType(node.type)
            const { width: w, height: h } = getNodeRenderedSize(node, fallback)
            const rect = { x: node.position.x, y: node.position.y, width: w, height: h }
            const otherBounds = getOtherNodesBounds(allNodesWithDragPosition, node.id)
            const { guides } = computeSmartGuideSnap(rect, otherBounds)
            setGuideLines(guides)
        },
        [smartGuides, nodes]
    )

    const onNodeDragStop = useCallback(() => {
        setGuideLines([])
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
            // Collect ALL selected SourceNodes with content
            const sourceNodesForTransform = sourceNodes.filter(sn =>
                selectedSourceNodeIds.some(n => n.id === sn.id) && !!sn.content
            )

            if (sourceNodesForTransform.length > 0) {
                setSelectedNodesForTransform(sourceNodesForTransform as any)
                setSelectedSourceNodeForTransform(null)

                const avgX = selectedSourceNodeIds.reduce((sum, n) => sum + (n.position?.x || 0), 0) / selectedSourceNodeIds.length
                const avgY = selectedSourceNodeIds.reduce((sum, n) => sum + (n.position?.y || 0), 0) / selectedSourceNodeIds.length
                setNewNodePosition({ x: avgX + 300, y: avgY })

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

    const topbarTarget = document.getElementById('topbar-context')

    return (
        <div className="relative w-full h-full">
            {/* Board toolbar rendered into TopBar via portal */}
            {topbarTarget && createPortal(
                <>
                    <span className="font-medium text-sm truncate max-w-[200px]">
                        {currentBoard?.name ?? 'Доска'}
                    </span>
                    <div className="w-px h-6 bg-border mx-1" />
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button size="sm" variant="outline" className="h-8 gap-1">
                                <Plus className="h-3.5 w-3.5" />
                                Добавить источник
                                <ChevronDown className="ml-1 h-3 w-3 opacity-50" />
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
                                className="h-8 gap-1 bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/20 text-blue-700 dark:text-blue-300"
                            >
                                <Wand2 className="h-3.5 w-3.5" />
                                Обработка
                            </Button>
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={handleVisualizeSelected}
                                className="h-8 gap-1 bg-purple-500/10 border-purple-500/30 hover:bg-purple-500/20 text-purple-700 dark:text-purple-300"
                            >
                                <TrendingUp className="h-3.5 w-3.5" />
                                Визуализация
                            </Button>
                        </>
                    )}
                    <span className="flex-1 min-w-2" aria-hidden />
                    <Button
                        variant={showGrid ? 'default' : 'ghost'}
                        size="icon"
                        className="h-7 w-7 shrink-0"
                        onClick={() => setShowGrid((g) => !g)}
                        title="Сетка"
                    >
                        <Grid3X3 className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                        variant={snapToGrid ? 'default' : 'ghost'}
                        size="icon"
                        className="h-7 w-7 shrink-0"
                        onClick={() => setSnapToGrid((s) => !s)}
                        title="Привязка к сетке"
                    >
                        <Magnet className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                        variant={smartGuides ? 'default' : 'ghost'}
                        size="icon"
                        className="h-7 w-7 shrink-0"
                        onClick={() => setSmartGuides((s) => !s)}
                        title="Умные направляющие"
                    >
                        <Ruler className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-8 w-8 p-0 shrink-0"
                        title="Обновить превью доски"
                        onClick={() => captureThumbnail(false)}
                        disabled={isCapturingThumbnail}
                    >
                        <Camera className="h-3.5 w-3.5" />
                    </Button>
                </>,
                topbarTarget,
            )}

            {/* React Flow Canvas — ref для захвата превью доски */}
            <div ref={flowContainerRef} className="relative w-full h-full">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onNodeDrag={onNodeDrag}
                    onNodeDragStop={onNodeDragStop}
                    onPaneClick={onPaneClick}
                    onDrop={onDrop}
                    onDragOver={onDragOver}
                    nodeTypes={nodeTypes}
                    edgeTypes={edgeTypes}
                    minZoom={0.5}
                    maxZoom={2}
                    defaultViewport={{ x: 0, y: 0, zoom: 1 }}
                    className="bg-muted/30"
                    selectNodesOnDrag={false}
                    panOnDrag={true}
                    selectionOnDrag={false}
                    selectionMode={SelectionMode.Partial}
                    onlyRenderVisibleElements={false}
                    selectionKeyCode="Shift"
                    connectionMode="loose"
                    connectOnClick={false}
                    snapGrid={snapToGrid ? [GRID_SIZE, GRID_SIZE] : undefined}
                    proOptions={{ hideAttribution: true }}
                >
                    {showGrid && <Background gap={GRID_SIZE} size={1} />}
                    <Controls />
                    <MiniMap nodeStrokeWidth={3} className="bg-background border border-border" />
                    {/* Умные направляющие: мост внутри ReactFlow порталит оверлей в контейнер, пиксели по transform */}
                    {guideLines.length > 0 && (
                        <GuideLinesBridge guideLines={guideLines} containerRef={flowContainerRef} />
                    )}
                </ReactFlow>
            </div>

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
                <p>✨ Выберите несколько элементов и нажмите Обработка для объединения данных</p>
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
                    onTransform={async (code, transformationId, description, chatHistory) => {
                        if (!boardId) return

                        console.log('🚀 onTransform called:', { code: code?.substring(0, 100), transformationId, description, chatHistoryLength: chatHistory?.length })

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
                                    chat_history: chatHistory || [],  // Save chat history for editing later
                                    selected_node_ids: selectedNodesForTransform.length > 0
                                        ? selectedNodesForTransform.map(n => n.id)
                                        : [sourceNodeId]
                                }
                            )

                            console.log('✅ transformExecute result:', result)
                            notify.success('Обработка выполнена успешно')
                            setShowTransformDialog(false)

                            // Refresh content nodes and edges to show the new node
                            await fetchContentNodes(boardId)
                            await fetchEdges(boardId)

                            // Refresh ProjectExplorer: Таблицы and Измерения sections
                            const projectId = useBoardStore.getState().currentBoard?.project_id
                            if (projectId) {
                                const allBoards = useBoardStore.getState().boards.filter(b => b.project_id === projectId)
                                useLibraryStore.getState().refreshProjectTree(projectId, allBoards)
                            }
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
