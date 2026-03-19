import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { ReactFlowProvider } from '@xyflow/react'
import { AppLayout } from '@/components/layout/AppLayout'
import { ProjectExplorer } from '@/components/ProjectExplorer'
import { AIAssistantPanel } from '@/components/board/AIAssistantPanel'
import { BoardCanvas } from '@/components/board/BoardCanvas'
import { FilterBar } from '@/components/filters/FilterBar'
import { FilterPanel } from '@/components/filters/FilterPanel'
import { useProjectStore } from '@/store/projectStore'
import { useBoardStore } from '@/store/boardStore'
import { useAIAssistantStore } from '@/store/aiAssistantStore'
import { useFilterStore } from '@/store/filterStore'

export function BoardPage() {
    const { projectId, boardId } = useParams<{ projectId: string; boardId: string }>()
    const { fetchProject } = useProjectStore()
    const { currentBoard, fetchBoard, isLoading } = useBoardStore()
    const { setSocket } = useAIAssistantStore()
    const { setContext, loadDimensions, loadPresets, activeFilters, setInitiatorContentNodeIds, getConditionsByInitiator } = useFilterStore()
    const widgetNodes = useBoardStore((s) => s.widgetNodes)

    // Виджеты-инициаторы получают полные данные (для подсветки выбранного сегмента)
    useEffect(() => {
        if (!boardId) return
        const ids: string[] = []
        for (const w of widgetNodes) {
            const sourceId = (w.config as Record<string, unknown>)?.sourceContentNodeId
            if (typeof sourceId === 'string' && getConditionsByInitiator(w.id).length > 0) {
                ids.push(sourceId)
            }
        }
        setInitiatorContentNodeIds(ids)
    }, [boardId, widgetNodes, activeFilters, getConditionsByInitiator, setInitiatorContentNodeIds])

    useEffect(() => {
        if (projectId) {
            fetchProject(projectId)
            loadDimensions(projectId)
            loadPresets(projectId)
        }
        if (boardId) {
            fetchBoard(boardId)
        }
    }, [projectId, boardId, fetchProject, fetchBoard, loadDimensions, loadPresets])

    // Set cross-filter context
    useEffect(() => {
        if (projectId && boardId) {
            setContext({ type: 'board', id: boardId, projectId })
        }
        return () => setContext(null)
    }, [projectId, boardId, setContext])

    if (isLoading || !currentBoard) {
        return (
            <AppLayout
                sidebar={<ProjectExplorer context="board" />}
                rightPanel={boardId ? <AIAssistantPanel contextId={boardId} scope="board" /> : undefined}
            >
                <div className="h-full flex items-center justify-center">
                    <p className="text-muted-foreground">Загрузка доски...</p>
                </div>
            </AppLayout>
        )
    }

    return (
        <AppLayout
            sidebar={<ProjectExplorer context="board" />}
            rightPanel={boardId ? <AIAssistantPanel contextId={boardId} scope="board" /> : undefined}
        >
            <div className="flex flex-col h-full min-h-0">
                <FilterBar />
                <div className="flex-1 min-h-0 overflow-hidden">
                    <ReactFlowProvider>
                        <BoardCanvas />
                    </ReactFlowProvider>
                </div>
            </div>
            <FilterPanel />
        </AppLayout>
    )
}
