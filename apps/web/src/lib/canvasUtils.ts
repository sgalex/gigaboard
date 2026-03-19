/**
 * Canvas utilities for node positioning and collision detection
 */

import { WidgetNode, CommentNode, SourceNode, ContentNode } from '@/types'

// Default node dimensions
export const NODE_DIMENSIONS = {
    sourceNode: { width: 300, height: 180 },
    contentNode: { width: 320, height: 220 },
    widgetNode: { width: 400, height: 300 },
    commentNode: { width: 300, height: 150 },
}

// Padding between nodes
const NODE_PADDING = 20
const GRID_SIZE = 50

// Type for any node with position
type PositionedNode = SourceNode | ContentNode | WidgetNode | CommentNode

interface NodeBounds {
    x: number
    y: number
    width: number
    height: number
}

/**
 * Get the bounding box of a node
 */
function getNodeBounds(node: PositionedNode): NodeBounds {
    let width: number
    let height: number

    // Determine node type and get dimensions
    if ('source_type' in node) {
        // SourceNode
        width = NODE_DIMENSIONS.sourceNode.width
        height = NODE_DIMENSIONS.sourceNode.height
    } else if ('parent_content_ids' in node) {
        // ContentNode
        width = NODE_DIMENSIONS.contentNode.width
        height = NODE_DIMENSIONS.contentNode.height
    } else if ('html_code' in node) {
        // WidgetNode
        width = node.width || NODE_DIMENSIONS.widgetNode.width
        height = node.height || NODE_DIMENSIONS.widgetNode.height
    } else {
        // CommentNode
        width = NODE_DIMENSIONS.commentNode.width
        height = NODE_DIMENSIONS.commentNode.height
    }

    return {
        x: node.x,
        y: node.y,
        width,
        height,
    }
}

/**
 * Check if two bounding boxes overlap (with padding)
 */
function boundsOverlap(a: NodeBounds, b: NodeBounds): boolean {
    return !(
        a.x + a.width + NODE_PADDING < b.x ||
        b.x + b.width + NODE_PADDING < a.x ||
        a.y + a.height + NODE_PADDING < b.y ||
        b.y + b.height + NODE_PADDING < a.y
    )
}

/**
 * Find a free position on the canvas for a new node
 * @param existingNodes - All existing nodes on the canvas
 * @param preferredX - Preferred X position (e.g., canvas center)
 * @param preferredY - Preferred Y position
 * @param nodeType - Type of node to place
 * @returns Free position { x, y }
 */
export function findFreePosition(
    existingNodes: PositionedNode[],
    preferredX: number = 100,
    preferredY: number = 100,
    nodeType: 'sourceNode' | 'contentNode' | 'widgetNode' | 'commentNode' = 'sourceNode'
): { x: number; y: number } {
    const dimensions = NODE_DIMENSIONS[nodeType]

    // If no existing nodes, use preferred position
    if (existingNodes.length === 0) {
        return { x: preferredX, y: preferredY }
    }

    // Try the preferred position first
    const preferredBounds: NodeBounds = {
        x: preferredX,
        y: preferredY,
        width: dimensions.width,
        height: dimensions.height,
    }

    const hasCollision = existingNodes.some(node =>
        boundsOverlap(preferredBounds, getNodeBounds(node))
    )

    if (!hasCollision) {
        return { x: preferredX, y: preferredY }
    }

    // Search in a spiral pattern from preferred position
    const maxDistance = 2000 // Maximum search distance
    const step = GRID_SIZE

    for (let distance = step; distance < maxDistance; distance += step) {
        // Try positions in a square pattern around the preferred position
        const positions = [
            // Right
            { x: preferredX + distance, y: preferredY },
            // Down
            { x: preferredX, y: preferredY + distance },
            // Left
            { x: preferredX - distance, y: preferredY },
            // Up
            { x: preferredX, y: preferredY - distance },
            // Diagonal: bottom-right
            { x: preferredX + distance, y: preferredY + distance },
            // Diagonal: bottom-left
            { x: preferredX - distance, y: preferredY + distance },
            // Diagonal: top-left
            { x: preferredX - distance, y: preferredY - distance },
            // Diagonal: top-right
            { x: preferredX + distance, y: preferredY - distance },
        ]

        for (const pos of positions) {
            const testBounds: NodeBounds = {
                x: pos.x,
                y: pos.y,
                width: dimensions.width,
                height: dimensions.height,
            }

            const hasCollision = existingNodes.some(node =>
                boundsOverlap(testBounds, getNodeBounds(node))
            )

            if (!hasCollision) {
                return pos
            }
        }
    }

    // If no free position found (very unlikely), place to the right of all nodes
    const rightmostNode = existingNodes.reduce((max, node) => {
        const bounds = getNodeBounds(node)
        const rightEdge = bounds.x + bounds.width
        return rightEdge > max ? rightEdge : max
    }, 0)

    return {
        x: rightmostNode + NODE_PADDING + 100,
        y: preferredY,
    }
}

/**
 * Snap position to grid
 */
export function snapToGrid(x: number, y: number, gridSize: number = GRID_SIZE): { x: number; y: number } {
    return {
        x: Math.round(x / gridSize) * gridSize,
        y: Math.round(y / gridSize) * gridSize,
    }
}
