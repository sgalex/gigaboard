/**
 * Sources Dialogs - модульные диалоги для каждого типа источника.
 * 
 * Архитектура:
 * - BaseSourceDialog - общая обёртка
 * - useSourceDialog - хук с общей логикой
 * - *SourceDialog - специфичные диалоги
 * - SourceDialogRouter - выбор диалога по типу
 * 
 * См. docs/SOURCE_NODE_CONCEPT_V2.md
 */

// Types
export * from './types'

// Base components
export { BaseSourceDialog } from './BaseSourceDialog'
export { useSourceDialog } from './useSourceDialog'

// Router
export { SourceDialogRouter } from './SourceDialogRouter'

// Individual dialogs
export { CSVSourceDialog } from './CSVSourceDialog'
export { JSONSourceDialog } from './JSONSourceDialog'
export { ExcelSourceDialog } from './ExcelSourceDialog'
export { DocumentSourceDialog } from './DocumentSourceDialog'
export { APISourceDialog } from './APISourceDialog'
export { DatabaseSourceDialog } from './DatabaseSourceDialog'
export { ResearchSourceDialog } from './ResearchSourceDialog'
export { ManualSourceDialog } from './ManualSourceDialog'
export { StreamSourceDialog } from './StreamSourceDialog'
