/**
 * Source Dialog Router - выбирает нужный диалог по типу источника.
 * 
 * Используется в BoardCanvas для открытия правильного диалога
 * при drag & drop из витрины источников.
 */
import { SourceType } from '@/types'
import { SourceDialogProps } from './types'
import { CSVSourceDialog } from './CSVSourceDialog'
import { JSONSourceDialog } from './JSONSourceDialog'
import { ExcelSourceDialog } from './ExcelSourceDialog'
import { DocumentSourceDialog } from './DocumentSourceDialog'
import { APISourceDialog } from './APISourceDialog'
import { DatabaseSourceDialog } from './DatabaseSourceDialog'
import { ResearchSourceDialog } from './ResearchSourceDialog'
import { ManualSourceDialog } from './ManualSourceDialog'
import { StreamSourceDialog } from './StreamSourceDialog'

interface SourceDialogRouterProps extends SourceDialogProps {
    sourceType: SourceType | string | null
}

/**
 * Роутер для диалогов источников.
 * Выбирает правильный диалог на основе sourceType.
 */
export function SourceDialogRouter({
    sourceType,
    open,
    onOpenChange,
    initialPosition
}: SourceDialogRouterProps) {
    if (!sourceType || !open) return null

    const dialogProps: SourceDialogProps = {
        open,
        onOpenChange,
        initialPosition,
    }

    // Map string to SourceType if needed
    const type = typeof sourceType === 'string' ? sourceType : sourceType

    switch (type) {
        case SourceType.CSV:
        case 'csv':
            return <CSVSourceDialog {...dialogProps} />

        case SourceType.JSON:
        case 'json':
            return <JSONSourceDialog {...dialogProps} />

        case SourceType.EXCEL:
        case 'excel':
            return <ExcelSourceDialog {...dialogProps} />

        case SourceType.DOCUMENT:
        case 'document':
            return <DocumentSourceDialog {...dialogProps} />

        case SourceType.API:
        case 'api':
            return <APISourceDialog {...dialogProps} />

        case SourceType.DATABASE:
        case 'database':
            return <DatabaseSourceDialog {...dialogProps} />

        case SourceType.RESEARCH:
        case 'research':
            return <ResearchSourceDialog {...dialogProps} />

        case SourceType.MANUAL:
        case 'manual':
            return <ManualSourceDialog {...dialogProps} />

        case SourceType.STREAM:
        case 'stream':
            return <StreamSourceDialog {...dialogProps} />

        default:
            console.warn(`Unknown source type: ${sourceType}`)
            return null
    }
}
