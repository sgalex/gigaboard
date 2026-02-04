/**
 * ResizableHandle - draggable divider for resizing panels
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface ResizableHandleProps {
    onResize: (delta: number) => void
    onReset?: () => void
    side: 'left' | 'right'
    className?: string
}

export function ResizableHandle({ onResize, onReset, side, className }: ResizableHandleProps) {
    const [isDragging, setIsDragging] = useState(false)
    const startXRef = useRef<number>(0)

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        e.preventDefault()
        setIsDragging(true)
        startXRef.current = e.clientX
    }, [])

    const handleDoubleClick = useCallback((e: React.MouseEvent) => {
        e.preventDefault()
        if (onReset) {
            onReset()
        }
    }, [onReset])

    useEffect(() => {
        if (!isDragging) return

        // Prevent text selection during drag
        document.body.style.userSelect = 'none'
        document.body.style.cursor = 'col-resize'

        const handleMouseMove = (e: MouseEvent) => {
            const delta = e.clientX - startXRef.current
            startXRef.current = e.clientX

            // For left panel, positive delta means growing (moving right)
            // For right panel, negative delta means growing (moving left)
            onResize(side === 'left' ? delta : -delta)
        }

        const handleMouseUp = () => {
            setIsDragging(false)
            document.body.style.userSelect = ''
            document.body.style.cursor = ''
        }

        document.addEventListener('mousemove', handleMouseMove)
        document.addEventListener('mouseup', handleMouseUp)

        return () => {
            document.removeEventListener('mousemove', handleMouseMove)
            document.removeEventListener('mouseup', handleMouseUp)
            document.body.style.userSelect = ''
            document.body.style.cursor = ''
        }
    }, [isDragging, onResize, side])

    return (
        <div
            className={cn(
                'group relative cursor-col-resize',
                // Invisible hit area for easier grabbing (6px wide)
                side === 'left' ? 'w-1.5 -mr-0.5' : 'w-1.5 -ml-0.5',
                className
            )}
            onMouseDown={handleMouseDown}
            onDoubleClick={handleDoubleClick}
            title="Перетащите для изменения размера, двойной клик для сброса"
            style={{ userSelect: 'none' }}
        >
            {/* Visual line - strictly 1px, grows on hover/drag */}
            <div
                className={cn(
                    'absolute inset-y-0 transition-all',
                    'left-1/2 -translate-x-1/2',
                    // Default: 1px
                    'w-px bg-border',
                    // Hover: slightly thicker and colored
                    'group-hover:w-[2px] group-hover:bg-primary/60',
                    // Dragging: thicker and more visible
                    isDragging && 'w-[3px] bg-primary'
                )}
            />
        </div>
    )
}
