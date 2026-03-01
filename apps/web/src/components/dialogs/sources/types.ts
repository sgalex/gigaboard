/**
 * Общие типы для диалогов источников данных.
 * 
 * См. docs/SOURCE_NODE_CONCEPT_V2.md
 */

import { SourceNode } from '@/types'

export interface SourceDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    initialPosition?: { x: number; y: number }
    existingSource?: SourceNode  // For edit mode
    mode?: 'create' | 'edit'  // Explicit mode
}

export interface SourceConfig {
    [key: string]: any
}

export interface CreateSourceResult {
    success: boolean
    error?: string
    sourceId?: string  // ID of created/updated source node
}
