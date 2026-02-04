import { memo } from 'react'
import { EdgeProps, getBezierPath, BaseEdge } from '@xyflow/react'

export const TransformationEdge = memo(({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    style = {},
    markerEnd,
}: EdgeProps) => {
    const [edgePath] = getBezierPath({
        sourceX,
        sourceY,
        sourcePosition,
        targetX,
        targetY,
        targetPosition,
    })

    return <BaseEdge path={edgePath} markerEnd={markerEnd} style={style as any} />
})

TransformationEdge.displayName = 'TransformationEdge'