import { memo } from 'react'
import { Handle, Position, NodeProps, NodeResizer } from '@xyflow/react'
import { MessageSquare, CheckCircle2 } from 'lucide-react'
import { CommentNode } from '@/types'
import { useBoardStore } from '@/store/boardStore'
import { useParams } from 'react-router-dom'

export const CommentNodeCard = memo(({ data, selected, width, height }: NodeProps) => {
    const node = data.commentNode as CommentNode
    const { boardId } = useParams<{ boardId: string }>()
    const { resolveCommentNode } = useBoardStore()

    // Use React Flow dimensions (updated in real-time during resize) or fallback to node dimensions
    const nodeWidth = width ?? node.width ?? 240
    const nodeHeight = height ?? node.height ?? 120

    const handleResolveToggle = (e: React.MouseEvent) => {
        e.stopPropagation()
        if (boardId) {
            resolveCommentNode(boardId, node.id, !node.is_resolved)
        }
    }

    return (
        <>
            <NodeResizer
                isVisible={selected}
                minWidth={180}
                minHeight={100}
                lineStyle={{ borderWidth: 0 }}
                handleStyle={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '2px',
                    backgroundColor: node.color || '#f59e0b',
                    border: '2px solid white',
                }}
            />
            <div
                className="bg-background border-2 rounded-lg shadow-lg"
                style={{
                    borderColor: node.color || '#f59e0b',
                    width: nodeWidth,
                    height: nodeHeight,
                    boxShadow: selected
                        ? `0 0 0 4px ${node.color || '#f59e0b'}99, 0 4px 6px -1px rgba(0, 0, 0, 0.1)`
                        : undefined,
                }}
            >
                {/* Header */}
                <div
                    className="text-white px-3 py-2 rounded-t-md flex items-center gap-2 justify-between"
                    style={{ backgroundColor: node.color || '#f59e0b' }}
                >
                    <div className="flex items-center gap-2 flex-1">
                        <MessageSquare className="h-4 w-4" />
                        <span className="text-sm font-medium">Comment</span>
                    </div>
                    <button
                        onClick={handleResolveToggle}
                        className={`p-0.5 rounded hover:bg-white/20 transition-colors ${node.is_resolved ? 'opacity-100' : 'opacity-50'
                            }`}
                        title={node.is_resolved ? 'Mark as unresolved' : 'Mark as resolved'}
                    >
                        <CheckCircle2
                            className={`h-4 w-4 ${node.is_resolved ? 'fill-current' : ''}`}
                        />
                    </button>
                </div>

                {/* Content */}
                <div
                    className="p-3 space-y-2"
                    style={{
                        userSelect: selected ? 'none' : 'auto',
                        pointerEvents: selected ? 'none' : 'auto'
                    }}
                >
                    {/* Render content based on format */}
                    {node.format_type === 'markdown' ? (
                        <div className="text-sm prose prose-sm max-w-none dark:prose-invert">
                            {/* For production, use a markdown renderer like react-markdown */}
                            <div className="whitespace-pre-wrap">{node.content}</div>
                        </div>
                    ) : (
                        <div className="text-sm whitespace-pre-wrap">{node.content}</div>
                    )}

                    {/* Resolved indicator */}
                    {node.is_resolved && node.resolved_at && (
                        <div className="mt-2 pt-2 border-t text-xs text-muted-foreground flex items-center gap-1">
                            <CheckCircle2 className="h-3 w-3" />
                            <span>
                                Resolved {new Date(node.resolved_at).toLocaleDateString()}
                            </span>
                        </div>
                    )}
                </div>

                {/* Connection handle */}
                <Handle
                    type="source"
                    position={Position.Right}
                    style={{
                        width: '10px',
                        height: '10px',
                        backgroundColor: node.color || '#f59e0b'
                    }}
                />
            </div>
        </>
    )
})

CommentNodeCard.displayName = 'CommentNodeCard'
