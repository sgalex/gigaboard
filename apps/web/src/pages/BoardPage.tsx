import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { ReactFlowProvider } from '@xyflow/react'
import { AppLayout } from '@/components/layout/AppLayout'
import { ProjectExplorer } from '@/components/ProjectExplorer'
import { AIAssistantPanel } from '@/components/board/AIAssistantPanel'
import { BoardCanvas } from '@/components/board/BoardCanvas'
import { useProjectStore } from '@/store/projectStore'
import { useBoardStore } from '@/store/boardStore'
import { useAIAssistantStore } from '@/store/aiAssistantStore'

export function BoardPage() {
    const { projectId, boardId } = useParams<{ projectId: string; boardId: string }>()
    const { fetchProject } = useProjectStore()
    const { currentBoard, fetchBoard, isLoading } = useBoardStore()
    const { setSocket } = useAIAssistantStore()

    useEffect(() => {
        if (projectId) {
            fetchProject(projectId)
        }
        if (boardId) {
            fetchBoard(boardId)
        }
    }, [projectId, boardId, fetchProject, fetchBoard])

    if (isLoading || !currentBoard) {
        return (
            <AppLayout
                sidebar={<ProjectExplorer />}
                rightPanel={boardId ? <AIAssistantPanel boardId={boardId} /> : undefined}
            >
                <div className="h-full flex items-center justify-center">
                    <p className="text-muted-foreground">Загрузка доски...</p>
                </div>
            </AppLayout>
        )
    }

    return (
        <AppLayout
            sidebar={<ProjectExplorer />}
            rightPanel={boardId ? <AIAssistantPanel boardId={boardId} /> : undefined}
        >
            <ReactFlowProvider>
                <BoardCanvas />
            </ReactFlowProvider>
        </AppLayout>
    )
}
