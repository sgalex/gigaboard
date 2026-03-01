/**
 * AppLayout - main application layout with TopBar, ProjectExplorer, and content area
 */
import { ReactNode, useCallback } from 'react'
import { TopBar } from './TopBar'
import { ProjectExplorer } from '../ProjectExplorer'
import { ResizableHandle } from './ResizableHandle'
import { useUIStore } from '@/store/uiStore'
import { cn } from '@/lib/utils'

interface AppLayoutProps {
    children: ReactNode
    showExplorer?: boolean
    sidebar?: ReactNode
    rightPanel?: ReactNode
}

const MIN_PANEL_WIDTH = 200
const MAX_PANEL_WIDTH = 800
const DEFAULT_LEFT_PANEL_WIDTH = 320
const DEFAULT_RIGHT_PANEL_WIDTH = 384

export function AppLayout({ children, showExplorer = true, sidebar, rightPanel }: AppLayoutProps) {
    const {
        isProjectExplorerOpen,
        isAIPanelOpen,
        leftPanelWidth,
        rightPanelWidth,
        setLeftPanelWidth,
        setRightPanelWidth,
    } = useUIStore()

    const handleLeftPanelResize = useCallback(
        (delta: number) => {
            const newWidth = Math.max(MIN_PANEL_WIDTH, Math.min(MAX_PANEL_WIDTH, leftPanelWidth + delta))
            setLeftPanelWidth(newWidth)
        },
        [leftPanelWidth, setLeftPanelWidth]
    )

    const handleRightPanelResize = useCallback(
        (delta: number) => {
            const newWidth = Math.max(MIN_PANEL_WIDTH, Math.min(MAX_PANEL_WIDTH, rightPanelWidth + delta))
            setRightPanelWidth(newWidth)
        },
        [rightPanelWidth, setRightPanelWidth]
    )

    const handleLeftPanelReset = useCallback(() => {
        setLeftPanelWidth(DEFAULT_LEFT_PANEL_WIDTH)
    }, [setLeftPanelWidth])

    const handleRightPanelReset = useCallback(() => {
        setRightPanelWidth(DEFAULT_RIGHT_PANEL_WIDTH)
    }, [setRightPanelWidth])

    return (
        <div className="flex h-screen flex-col bg-background">
            <TopBar />

            <div className="flex flex-1 overflow-hidden">
                {/* Left Sidebar - Project Explorer */}
                {(showExplorer || sidebar) && (
                    <>
                        <aside
                            className={cn(
                                'border-r border-border bg-card transition-all duration-300',
                                isProjectExplorerOpen ? 'opacity-100' : 'w-0 opacity-0'
                            )}
                            style={{
                                width: isProjectExplorerOpen ? `${leftPanelWidth}px` : '0px',
                            }}
                        >
                            {isProjectExplorerOpen && (sidebar || <ProjectExplorer />)}
                        </aside>
                        {isProjectExplorerOpen && (
                            <ResizableHandle
                                side="left"
                                onResize={handleLeftPanelResize}
                                onReset={handleLeftPanelReset}
                                className="z-10"
                            />
                        )}
                    </>
                )}

                {/* Main content area — min-h-0 so flex item doesn't grow with content and cause page scroll */}
                <main className="flex-1 min-h-0 overflow-auto">
                    {children}
                </main>

                {/* Right Panel - AI Assistant */}
                {rightPanel && (
                    <>
                        {isAIPanelOpen && (
                            <ResizableHandle
                                side="right"
                                onResize={handleRightPanelResize}
                                onReset={handleRightPanelReset}
                                className="z-10"
                            />
                        )}
                        <aside
                            className={cn(
                                'border-l border-border bg-card transition-all duration-300 overflow-hidden',
                                isAIPanelOpen ? 'opacity-100' : 'w-0 opacity-0'
                            )}
                            style={{
                                width: isAIPanelOpen ? `${rightPanelWidth}px` : '0px',
                            }}
                        >
                            {isAIPanelOpen && rightPanel}
                        </aside>
                    </>
                )}
            </div>
        </div>
    )
}
