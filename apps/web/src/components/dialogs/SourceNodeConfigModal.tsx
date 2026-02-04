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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SourceType } from '@/types'
import { useBoardStore } from '@/store/boardStore'
import { useAuthStore } from '@/store/authStore'
import { useParams } from 'react-router-dom'
import { notify } from '@/store/notificationStore'
import { filesAPI } from '@/services/api'

interface SourceNodeConfigModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    initialPosition?: { x: number; y: number }
    initialSourceType?: string | null
}

export function SourceNodeConfigModal({
    open,
    onOpenChange,
    initialPosition = { x: 100, y: 100 },
    initialSourceType = null,
}: SourceNodeConfigModalProps) {
    const { boardId } = useParams<{ boardId: string }>()
    const { user } = useAuthStore()
    const { createSourceNode } = useBoardStore()

    // Map string to SourceType enum, default to CSV
    const getInitialSourceType = (): SourceType => {
        if (!initialSourceType) return SourceType.CSV
        const typeMap: Record<string, SourceType> = {
            csv: SourceType.CSV,
            json: SourceType.JSON,
            excel: SourceType.EXCEL,
            document: SourceType.DOCUMENT,
            api: SourceType.API,
            database: SourceType.DATABASE,
            research: SourceType.RESEARCH,
            manual: SourceType.MANUAL,
            stream: SourceType.STREAM,
        }
        return typeMap[initialSourceType] || SourceType.CSV
    }

    const [sourceType, setSourceType] = useState<SourceType>(getInitialSourceType())

    // Update source type when initialSourceType changes (from drop)
    useEffect(() => {
        if (open && initialSourceType) {
            setSourceType(getInitialSourceType())
        }
    }, [open, initialSourceType])

    // FILE config
    const [file, setFile] = useState<File | null>(null)

    // DATABASE config
    const [databaseType, setDatabaseType] = useState('postgresql')
    // PostgreSQL/MySQL/ClickHouse fields
    const [dbHost, setDbHost] = useState('')
    const [dbPort, setDbPort] = useState('')
    const [dbName, setDbName] = useState('')
    const [dbUser, setDbUser] = useState('')
    const [dbPassword, setDbPassword] = useState('')
    // MongoDB fields
    const [mongoUri, setMongoUri] = useState('')
    const [mongoDatabase, setMongoDatabase] = useState('')
    // SQLite fields
    const [sqlitePath, setSqlitePath] = useState('')
    // Connection test
    const [isTestingConnection, setIsTestingConnection] = useState(false)
    const [connectionTested, setConnectionTested] = useState(false)
    const [availableTables, setAvailableTables] = useState<string[]>([])
    const [selectedTables, setSelectedTables] = useState<string[]>([])

    // API config
    const [apiUrl, setApiUrl] = useState('')
    const [apiMethod, setApiMethod] = useState('GET')
    const [apiHeaders, setApiHeaders] = useState('')
    const [apiBody, setApiBody] = useState('')

    // PROMPT config
    const [prompt, setPrompt] = useState('')

    // STREAM config
    const [streamUrl, setStreamUrl] = useState('')
    const [streamType, setStreamType] = useState('websocket')

    // MANUAL config - spreadsheet-like table
    const [manualColumns, setManualColumns] = useState<string[]>(['Column 1', 'Column 2', 'Column 3'])
    const [manualRows, setManualRows] = useState<Record<string, string>[]>([
        { 'Column 1': '', 'Column 2': '', 'Column 3': '' },
        { 'Column 1': '', 'Column 2': '', 'Column 3': '' },
        { 'Column 1': '', 'Column 2': '', 'Column 3': '' },
    ])

    const [isLoading, setIsLoading] = useState(false)

    const handleCreate = async () => {
        if (!boardId) return

        setIsLoading(true)

        try {
            // Auto-generate name based on source type
            const nameMap: Record<SourceType, string> = {
                [SourceType.CSV]: 'CSV файл',
                [SourceType.JSON]: 'JSON файл',
                [SourceType.EXCEL]: 'Excel файл',
                [SourceType.DOCUMENT]: 'Документ',
                [SourceType.API]: 'API',
                [SourceType.DATABASE]: 'База данных',
                [SourceType.RESEARCH]: 'AI Research',
                [SourceType.MANUAL]: 'Ручной ввод',
                [SourceType.STREAM]: 'Стрим',
            }
            const autoName = nameMap[sourceType] || 'Источник данных'

            // Build config based on source type
            let config: Record<string, any> = {}

            switch (sourceType) {
                case SourceType.CSV:
                case SourceType.JSON:
                case SourceType.EXCEL:
                case SourceType.DOCUMENT:
                    // File-based sources
                    if (!file) {
                        notify.error('Выберите файл для загрузки')
                        return
                    }

                    // Upload file to backend first
                    notify.info('Загрузка файла...', { title: 'Обработка' })
                    try {
                        const uploadResponse = await filesAPI.upload(file)
                        const uploadedFile = uploadResponse.data

                        config = {
                            file_id: uploadedFile.file_id,
                            filename: uploadedFile.filename,
                            mime_type: uploadedFile.mime_type,
                            size_bytes: uploadedFile.size_bytes,
                        }

                        notify.success(`Файл "${file.name}" загружен`, { title: 'Успех' })
                    } catch (error) {
                        notify.error('Не удалось загрузить файл', { title: 'Ошибка' })
                        console.error('File upload error:', error)
                        return
                    }
                    break

                case SourceType.DATABASE:
                    if (!connectionTested) {
                        notify.error('Сначала протестируйте подключение к БД')
                        return
                    }
                    if (selectedTables.length === 0) {
                        notify.error('Выберите хотя бы одну таблицу')
                        return
                    }

                    // Build connection config based on DB type
                    let dbConfig: Record<string, any> = { database_type: databaseType }

                    if (databaseType === 'mongodb') {
                        dbConfig.uri = mongoUri
                        dbConfig.database = mongoDatabase
                    } else if (databaseType === 'sqlite') {
                        dbConfig.path = sqlitePath
                    } else {
                        // PostgreSQL, MySQL, ClickHouse
                        dbConfig.host = dbHost
                        dbConfig.port = parseInt(dbPort)
                        dbConfig.database = dbName
                        dbConfig.user = dbUser
                        dbConfig.password = dbPassword
                    }

                    config = {
                        ...dbConfig,
                        tables: selectedTables,
                    }
                    break

                case SourceType.API:
                    if (!apiUrl.trim()) {
                        notify.error('Укажите URL API')
                        return
                    }
                    config = {
                        url: apiUrl,
                        method: apiMethod,
                        headers: apiHeaders ? JSON.parse(apiHeaders) : {},
                        body: apiBody || undefined,
                    }
                    break

                case SourceType.RESEARCH:
                    if (!prompt.trim()) {
                        notify.error('Введите запрос для AI Research')
                        return
                    }
                    config = {
                        initial_prompt: prompt,
                        context: {},
                    }
                    break

                case SourceType.STREAM:
                    if (!streamUrl.trim()) {
                        notify.error('Укажите URL стрима')
                        return
                    }
                    config = {
                        stream_url: streamUrl,
                        stream_type: streamType,
                    }
                    break

                case SourceType.MANUAL:
                    // Validate that at least one cell has data
                    const hasData = manualRows.some(row =>
                        Object.values(row).some(cell => cell.trim() !== '')
                    )
                    if (!hasData) {
                        notify.error('Введите данные в таблицу')
                        return
                    }
                    config = {
                        columns: manualColumns,
                        data: manualRows,
                        row_count: manualRows.length,
                        format: 'table',
                    }
                    break
            }

            if (!user) {
                notify.error('Пользователь не авторизован')
                return
            }

            await createSourceNode(boardId, {
                board_id: boardId,
                source_type: sourceType,
                config: config,
                metadata: {
                    name: autoName,
                },
                position: initialPosition,
                created_by: user.id,
            })

            // Reset and close
            resetForm()
            onOpenChange(false)
        } catch (error: any) {
            console.error('Failed to create SourceNode:', error)
            notify.error(error.response?.data?.detail || 'Не удалось создать источник данных')
        } finally {
            setIsLoading(false)
        }
    }

    const testDatabaseConnection = async () => {
        setIsTestingConnection(true)
        try {
            // Build connection params
            let connectionParams: Record<string, any> = { database_type: databaseType }

            if (databaseType === 'mongodb') {
                if (!mongoUri.trim() || !mongoDatabase.trim()) {
                    notify.error('Укажите URI и название базы данных')
                    return
                }
                connectionParams.uri = mongoUri
                connectionParams.database = mongoDatabase
            } else if (databaseType === 'sqlite') {
                if (!sqlitePath.trim()) {
                    notify.error('Укажите путь к файлу БД')
                    return
                }
                connectionParams.path = sqlitePath
            } else {
                // PostgreSQL, MySQL, ClickHouse
                if (!dbHost.trim() || !dbPort.trim() || !dbName.trim() || !dbUser.trim()) {
                    notify.error('Заполните все обязательные поля подключения')
                    return
                }
                connectionParams.host = dbHost
                connectionParams.port = parseInt(dbPort)
                connectionParams.database = dbName
                connectionParams.user = dbUser
                connectionParams.password = dbPassword
            }

            // Call backend to test connection and get tables
            const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
            const response = await fetch(`${API_URL}/api/v1/database/test-connection`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(connectionParams),
            })

            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.detail || 'Не удалось подключиться к БД')
            }

            const data = await response.json()
            setAvailableTables(data.tables || [])
            setConnectionTested(true)
            notify.success(`Подключение успешно. Найдено таблиц: ${data.tables.length}`)
        } catch (error: any) {
            console.error('Database connection test failed:', error)
            notify.error(error.message || 'Ошибка подключения к БД')
            setConnectionTested(false)
            setAvailableTables([])
        } finally {
            setIsTestingConnection(false)
        }
    }

    const toggleTableSelection = (table: string) => {
        setSelectedTables(prev =>
            prev.includes(table)
                ? prev.filter(t => t !== table)
                : [...prev, table]
        )
    }

    const selectAllTables = () => {
        setSelectedTables(availableTables)
    }

    const deselectAllTables = () => {
        setSelectedTables([])
    }

    const resetForm = () => {
        setFile(null)
        setDbHost('')
        setDbPort('')
        setDbName('')
        setDbUser('')
        setDbPassword('')
        setMongoUri('')
        setMongoDatabase('')
        setSqlitePath('')
        setConnectionTested(false)
        setAvailableTables([])
        setSelectedTables([])
        setApiUrl('')
        setApiHeaders('')
        setPrompt('')
        setStreamUrl('')
        // Reset manual table to initial state
        setManualColumns(['Column 1', 'Column 2', 'Column 3'])
        setManualRows([
            { 'Column 1': '', 'Column 2': '', 'Column 3': '' },
            { 'Column 1': '', 'Column 2': '', 'Column 3': '' },
            { 'Column 1': '', 'Column 2': '', 'Column 3': '' },
        ])
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Создать источник данных</DialogTitle>
                    <DialogDescription>
                        Настройте новый источник данных для извлечения информации из различных источников
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Source Type Selection */}
                    <div className="space-y-2">
                        <Label htmlFor="sourceType">Тип источника *</Label>
                        <Select
                            value={sourceType}
                            onValueChange={(value) => setSourceType(value as SourceType)}
                        >
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value={SourceType.CSV}>📊 CSV файл</SelectItem>
                                <SelectItem value={SourceType.JSON}>📋 JSON файл</SelectItem>
                                <SelectItem value={SourceType.EXCEL}>📗 Excel файл</SelectItem>
                                <SelectItem value={SourceType.DOCUMENT}>📄 Документ (PDF, DOCX, TXT)</SelectItem>
                                <SelectItem value={SourceType.API}>🔗 REST API</SelectItem>
                                <SelectItem value={SourceType.DATABASE}>🗄️ База данных</SelectItem>
                                <SelectItem value={SourceType.RESEARCH}>🔍 AI Research</SelectItem>
                                <SelectItem value={SourceType.MANUAL}>✏️ Ручной ввод</SelectItem>
                                <SelectItem value={SourceType.STREAM} disabled>📡 Стрим (скоро)</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Source-specific configuration */}
                    <Tabs value={sourceType} className="w-full">
                        {/* CSV Tab */}
                        <TabsContent value={SourceType.CSV} className="space-y-4 mt-4">
                            <div className="space-y-2">
                                <Label htmlFor="file">Выберите CSV файл *</Label>
                                <Input
                                    id="file"
                                    type="file"
                                    accept=".csv"
                                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                                    className="cursor-pointer"
                                />
                                {file && (
                                    <p className="text-xs text-muted-foreground">
                                        Выбран: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                                    </p>
                                )}
                            </div>
                        </TabsContent>

                        {/* JSON Tab */}
                        <TabsContent value={SourceType.JSON} className="space-y-4 mt-4">
                            <div className="space-y-2">
                                <Label htmlFor="file">Выберите JSON файл *</Label>
                                <Input
                                    id="file"
                                    type="file"
                                    accept=".json"
                                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                                    className="cursor-pointer"
                                />
                                {file && (
                                    <p className="text-xs text-muted-foreground">
                                        Выбран: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                                    </p>
                                )}
                            </div>
                        </TabsContent>

                        {/* Excel Tab */}
                        <TabsContent value={SourceType.EXCEL} className="space-y-4 mt-4">
                            <div className="space-y-2">
                                <Label htmlFor="file">Выберите Excel файл *</Label>
                                <Input
                                    id="file"
                                    type="file"
                                    accept=".xlsx,.xls"
                                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                                    className="cursor-pointer"
                                />
                                {file && (
                                    <p className="text-xs text-muted-foreground">
                                        Выбран: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                                    </p>
                                )}
                            </div>
                        </TabsContent>

                        {/* Document Tab */}
                        <TabsContent value={SourceType.DOCUMENT} className="space-y-4 mt-4">
                            <div className="space-y-2">
                                <Label htmlFor="file">Выберите документ *</Label>
                                <Input
                                    id="file"
                                    type="file"
                                    accept=".pdf,.docx,.txt"
                                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                                    className="cursor-pointer"
                                />
                                {file && (
                                    <p className="text-xs text-muted-foreground">
                                        Выбран: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                                    </p>
                                )}
                            </div>
                        </TabsContent>

                        {/* RESEARCH Tab */}
                        <TabsContent value={SourceType.RESEARCH} className="space-y-4 mt-4">
                            <div className="space-y-2">
                                <Label htmlFor="prompt">Запрос для AI Research *</Label>
                                <Textarea
                                    id="prompt"
                                    placeholder="Опишите, какие данные нужно найти и структурировать..."
                                    value={prompt}
                                    onChange={(e) => setPrompt(e.target.value)}
                                    rows={4}
                                />
                                <p className="text-xs text-muted-foreground">
                                    AI агенты выполнят поиск и структурируют данные в таблицу
                                </p>
                            </div>
                        </TabsContent>

                        {/* DATABASE Tab */}
                        <TabsContent value={SourceType.DATABASE} className="space-y-4 mt-4">
                            <div className="space-y-2">
                                <Label htmlFor="databaseType">Тип БД *</Label>
                                <Select
                                    value={databaseType}
                                    onValueChange={(value) => {
                                        setDatabaseType(value)
                                        setConnectionTested(false)
                                        setAvailableTables([])
                                        setSelectedTables([])
                                    }}
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="postgresql">PostgreSQL</SelectItem>
                                        <SelectItem value="mysql">MySQL</SelectItem>
                                        <SelectItem value="clickhouse">ClickHouse</SelectItem>
                                        <SelectItem value="mongodb">MongoDB</SelectItem>
                                        <SelectItem value="sqlite">SQLite</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* PostgreSQL, MySQL, ClickHouse fields */}
                            {['postgresql', 'mysql', 'clickhouse'].includes(databaseType) && (
                                <>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="dbHost">Хост *</Label>
                                            <Input
                                                id="dbHost"
                                                placeholder="localhost"
                                                value={dbHost}
                                                onChange={(e) => setDbHost(e.target.value)}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="dbPort">Порт *</Label>
                                            <Input
                                                id="dbPort"
                                                placeholder={databaseType === 'clickhouse' ? '9000' : databaseType === 'mysql' ? '3306' : '5432'}
                                                value={dbPort}
                                                onChange={(e) => setDbPort(e.target.value)}
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="dbName">Название базы *</Label>
                                        <Input
                                            id="dbName"
                                            placeholder="my_database"
                                            value={dbName}
                                            onChange={(e) => setDbName(e.target.value)}
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="dbUser">Пользователь *</Label>
                                            <Input
                                                id="dbUser"
                                                placeholder="username"
                                                value={dbUser}
                                                onChange={(e) => setDbUser(e.target.value)}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="dbPassword">Пароль</Label>
                                            <Input
                                                id="dbPassword"
                                                type="password"
                                                placeholder="••••••••"
                                                value={dbPassword}
                                                onChange={(e) => setDbPassword(e.target.value)}
                                            />
                                        </div>
                                    </div>
                                </>
                            )}

                            {/* MongoDB fields */}
                            {databaseType === 'mongodb' && (
                                <>
                                    <div className="space-y-2">
                                        <Label htmlFor="mongoUri">Connection URI *</Label>
                                        <Input
                                            id="mongoUri"
                                            type="password"
                                            placeholder="mongodb://user:pass@localhost:27017"
                                            value={mongoUri}
                                            onChange={(e) => setMongoUri(e.target.value)}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="mongoDatabase">База данных *</Label>
                                        <Input
                                            id="mongoDatabase"
                                            placeholder="my_database"
                                            value={mongoDatabase}
                                            onChange={(e) => setMongoDatabase(e.target.value)}
                                        />
                                    </div>
                                </>
                            )}

                            {/* SQLite fields */}
                            {databaseType === 'sqlite' && (
                                <div className="space-y-2">
                                    <Label htmlFor="sqlitePath">Путь к файлу БД *</Label>
                                    <Input
                                        id="sqlitePath"
                                        placeholder="/path/to/database.db"
                                        value={sqlitePath}
                                        onChange={(e) => setSqlitePath(e.target.value)}
                                    />
                                </div>
                            )}

                            {/* Test Connection Button */}
                            <Button
                                type="button"
                                onClick={testDatabaseConnection}
                                disabled={isTestingConnection}
                                variant="outline"
                                className="w-full"
                            >
                                {isTestingConnection ? 'Подключение...' : connectionTested ? '✓ Подключено' : 'Проверить подключение'}
                            </Button>

                            {/* Tables Preview */}
                            {connectionTested && availableTables.length > 0 && (
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label>Доступные таблицы ({availableTables.length})</Label>
                                        <div className="space-x-2">
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={selectAllTables}
                                            >
                                                Выбрать все
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={deselectAllTables}
                                            >
                                                Снять выбор
                                            </Button>
                                        </div>
                                    </div>
                                    <div className="border rounded-md p-3 max-h-48 overflow-y-auto space-y-2">
                                        {availableTables.map((table) => (
                                            <label
                                                key={table}
                                                className="flex items-center space-x-2 cursor-pointer hover:bg-accent p-2 rounded"
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={selectedTables.includes(table)}
                                                    onChange={() => toggleTableSelection(table)}
                                                    className="cursor-pointer"
                                                />
                                                <span className="text-sm font-mono">{table}</span>
                                            </label>
                                        ))}
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Выбрано: {selectedTables.length} из {availableTables.length}
                                    </p>
                                </div>
                            )}
                        </TabsContent>

                        {/* API Tab */}
                        <TabsContent value={SourceType.API} className="space-y-4 mt-4">
                            <div className="space-y-2">
                                <Label htmlFor="apiUrl">URL API *</Label>
                                <Input
                                    id="apiUrl"
                                    placeholder="https://api.example.com/data"
                                    value={apiUrl}
                                    onChange={(e) => setApiUrl(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="apiMethod">Метод *</Label>
                                <Select value={apiMethod} onValueChange={setApiMethod}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="GET">GET</SelectItem>
                                        <SelectItem value="POST">POST</SelectItem>
                                        <SelectItem value="PUT">PUT</SelectItem>
                                        <SelectItem value="DELETE">DELETE</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="apiHeaders">Заголовки (JSON)</Label>
                                <Textarea
                                    id="apiHeaders"
                                    placeholder='{"Authorization": "Bearer токен"}'
                                    value={apiHeaders}
                                    onChange={(e) => setApiHeaders(e.target.value)}
                                    rows={3}
                                    className="font-mono text-sm"
                                />
                            </div>
                            {/* Body field for POST/PUT/DELETE/PATCH */}
                            {['POST', 'PUT', 'DELETE', 'PATCH'].includes(apiMethod) && (
                                <div className="space-y-2">
                                    <Label htmlFor="apiBody">Тело запроса (JSON)</Label>
                                    <Textarea
                                        id="apiBody"
                                        placeholder='{"key": "value", "data": [1, 2, 3]}'
                                        value={apiBody}
                                        onChange={(e) => setApiBody(e.target.value)}
                                        rows={5}
                                        className="font-mono text-sm"
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Введите JSON для тела {apiMethod} запроса
                                    </p>
                                </div>
                            )}
                        </TabsContent>

                        {/* MANUAL Tab */}
                        <TabsContent value={SourceType.MANUAL} className="space-y-4 mt-4">
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <Label>Таблица данных</Label>
                                    <div className="flex gap-2">
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => {
                                                const newColName = `Column ${manualColumns.length + 1}`
                                                setManualColumns([...manualColumns, newColName])
                                                setManualRows(manualRows.map(row => ({ ...row, [newColName]: '' })))
                                            }}
                                        >
                                            + Колонка
                                        </Button>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => {
                                                const newRow: Record<string, string> = {}
                                                manualColumns.forEach(col => newRow[col] = '')
                                                setManualRows([...manualRows, newRow])
                                            }}
                                        >
                                            + Строка
                                        </Button>
                                    </div>
                                </div>

                                <div className="border rounded-lg overflow-auto max-h-96">
                                    <table className="w-full text-sm">
                                        <thead className="bg-muted">
                                            <tr>
                                                <th className="w-10 p-2 text-center">#</th>
                                                {manualColumns.map((col, colIndex) => (
                                                    <th key={colIndex} className="p-2 border-l">
                                                        <div className="flex items-center gap-2">
                                                            <Input
                                                                value={col}
                                                                onChange={(e) => {
                                                                    const oldName = manualColumns[colIndex]
                                                                    const newColumns = [...manualColumns]
                                                                    newColumns[colIndex] = e.target.value
                                                                    setManualColumns(newColumns)
                                                                    // Rename keys in rows
                                                                    setManualRows(manualRows.map(row => {
                                                                        const newRow = { ...row }
                                                                        newRow[e.target.value] = row[oldName] || ''
                                                                        delete newRow[oldName]
                                                                        return newRow
                                                                    }))
                                                                }}
                                                                className="h-7 text-xs font-semibold"
                                                                placeholder="Имя колонки"
                                                            />
                                                            {manualColumns.length > 1 && (
                                                                <Button
                                                                    type="button"
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    className="h-6 w-6 p-0"
                                                                    onClick={() => {
                                                                        const newColumns = manualColumns.filter((_, i) => i !== colIndex)
                                                                        setManualColumns(newColumns)
                                                                        setManualRows(manualRows.map(row => {
                                                                            const newRow = { ...row }
                                                                            delete newRow[col]
                                                                            return newRow
                                                                        }))
                                                                    }}
                                                                >
                                                                    ×
                                                                </Button>
                                                            )}
                                                        </div>
                                                    </th>
                                                ))}
                                                <th className="w-10 p-2 border-l"></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {manualRows.map((row, rowIndex) => (
                                                <tr key={rowIndex} className="hover:bg-muted/50">
                                                    <td className="p-2 text-center text-muted-foreground">{rowIndex + 1}</td>
                                                    {manualColumns.map((col, colIndex) => (
                                                        <td key={colIndex} className="p-1 border-l">
                                                            <Input
                                                                value={row[col] || ''}
                                                                onChange={(e) => {
                                                                    const newRows = [...manualRows]
                                                                    newRows[rowIndex][col] = e.target.value
                                                                    setManualRows(newRows)
                                                                }}
                                                                className="h-8 text-xs"
                                                                placeholder="Значение"
                                                            />
                                                        </td>
                                                    ))}
                                                    <td className="p-2 text-center border-l">
                                                        {manualRows.length > 1 && (
                                                            <Button
                                                                type="button"
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-6 w-6 p-0"
                                                                onClick={() => {
                                                                    setManualRows(manualRows.filter((_, i) => i !== rowIndex))
                                                                }}
                                                            >
                                                                ×
                                                            </Button>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>

                                <p className="text-xs text-muted-foreground">
                                    💡 Совет: Можно скопировать данные из Excel/Google Sheets и вставить в ячейки.
                                    Строк: {manualRows.length}, Колонок: {manualColumns.length}
                                </p>
                            </div>
                        </TabsContent>
                    </Tabs>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
                        Отмена
                    </Button>
                    <Button onClick={handleCreate} disabled={isLoading}>
                        {isLoading ? 'Создание...' : 'Создать источник'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
