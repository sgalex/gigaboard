import { useState, useEffect } from 'react'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useBoardStore } from '@/store/boardStore'
import { useParams } from 'react-router-dom'
import { notify } from '@/store/notificationStore'
import { AlertCircle, Info } from 'lucide-react'

interface TransformCodeEditorProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    sourceContentIds: string[]
    initialPosition?: { x: number; y: number }
}

export function TransformCodeEditor({
    open,
    onOpenChange,
    sourceContentIds,
    initialPosition = { x: 100, y: 100 },
}: TransformCodeEditorProps) {
    const { boardId } = useParams<{ boardId: string }>()
    const { contentNodes, createContentNode } = useBoardStore()

    const [name, setName] = useState('')
    const [code, setCode] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // Get source content nodes to show available DataFrames
    const sourceContents = contentNodes.filter((cn) =>
        sourceContentIds.includes(cn.id)
    )

    // Generate example code based on source contents
    useEffect(() => {
        if (sourceContents.length > 0 && !code) {
            const exampleCode = generateExampleCode(sourceContents.length)
            setCode(exampleCode)
        }
    }, [sourceContents.length])

    const generateExampleCode = (numSources: number): string => {
        if (numSources === 1) {
            return `# Available DataFrames: df0
# Transform the data
result = df0.copy()
result['new_column'] = result['existing_column'] * 2
result = result.sort_values('new_column', ascending=False)`
        } else if (numSources === 2) {
            return `# Available DataFrames: df0, df1
# Join two DataFrames
import pandas as pd
result = pd.merge(df0, df1, on='id', how='inner')
result['combined'] = result['col_x'] + result['col_y']`
        } else {
            return `# Available DataFrames: ${Array.from({ length: numSources }, (_, i) => `df${i}`).join(', ')}
# Combine multiple DataFrames
import pandas as pd
result = pd.concat([df0, df1, df2], ignore_index=True)
result = result.drop_duplicates()`
        }
    }

    const handleTransform = async () => {
        if (!boardId) return

        if (!name.trim()) {
            notify.error('Please enter a name for the transformation')
            return
        }

        if (!code.trim()) {
            notify.error('Please enter transformation code')
            return
        }

        setIsLoading(true)
        setError(null)

        try {
            // Call transform API
            const response = await fetch(
                `${import.meta.env.VITE_API_URL}/api/v1/content-nodes/transform`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        board_id: boardId,
                        source_content_ids: sourceContentIds,
                        code: code,
                        metadata: {
                            name: name,
                        },
                        position: initialPosition,
                    }),
                }
            )

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Transformation failed')
            }

            const newContentNode = await response.json()

            // Add to store
            await createContentNode(boardId, newContentNode)

            notify.success('Transformation executed successfully')

            // Reset and close
            setName('')
            setCode('')
            setError(null)
            onOpenChange(false)
        } catch (error: any) {
            console.error('Transformation error:', error)
            setError(error.message || 'Failed to execute transformation')
            notify.error(error.message || 'Transformation failed')
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
                <DialogHeader>
                    <DialogTitle>Transform Data</DialogTitle>
                    <DialogDescription>
                        Write Python code to transform and combine data. Output must be a DataFrame named 'result' or 'df'.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto space-y-4 py-4">
                    {/* Basic Info */}
                    <div className="space-y-2">
                        <Label htmlFor="transformName">Transformation Name *</Label>
                        <Input
                            id="transformName"
                            placeholder="My Data Transformation"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>

                    {/* Available DataFrames */}
                    <div className="space-y-2">
                        <Label>Available DataFrames</Label>
                        <div className="flex flex-wrap gap-2">
                            {sourceContents.map((content, idx) => (
                                <Badge key={content.id} variant="secondary">
                                    df{idx} - {content.metadata?.name || `Content ${content.id.slice(0, 8)}`}
                                </Badge>
                            ))}
                        </div>
                        <Alert>
                            <Info className="h-4 w-4" />
                            <AlertDescription>
                                Each source ContentNode is available as a DataFrame: df0, df1, df2, etc.
                                Your code must output a variable named 'result' or 'df'.
                            </AlertDescription>
                        </Alert>
                    </div>

                    {/* Code Editor */}
                    <div className="space-y-2 flex-1">
                        <Label htmlFor="code">Python Code *</Label>
                        <Textarea
                            id="code"
                            value={code}
                            onChange={(e) => setCode(e.target.value)}
                            placeholder="# Write your transformation code here"
                            className="font-mono text-sm min-h-[300px] resize-none"
                            spellCheck={false}
                        />
                    </div>

                    {/* Error Display */}
                    {error && (
                        <Alert variant="destructive">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    {/* Code Examples */}
                    <div className="space-y-2">
                        <Label>Common Operations</Label>
                        <div className="bg-muted p-3 rounded-md text-xs font-mono space-y-1">
                            <div># Filter: result = df0[df0['column'] &gt; 10]</div>
                            <div># Join: result = pd.merge(df0, df1, on='id')</div>
                            <div># Group: result = df0.groupby('category').sum()</div>
                            <div># Concat: result = pd.concat([df0, df1])</div>
                            <div># Add column: result = df0.copy(); result['new'] = df0['a'] + df0['b']</div>
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
                        Cancel
                    </Button>
                    <Button onClick={handleTransform} disabled={isLoading}>
                        {isLoading ? 'Executing...' : 'Execute Transformation'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
