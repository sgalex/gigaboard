/**
 * Database Source Dialog — двухпанельный диалог для подключения к БД.
 *
 * Левая панель:  настройки подключения + дерево схем/таблиц (выбор чекбоксами)
 * Правая панель: выбранные таблицы (клик → предпросмотр, удаление, настройки per-table)
 *
 * Per-table настройки (суб-диалог):
 *   - WHERE clause
 *   - Лимит строк
 *   - Выбор столбцов + переименование
 *
 * См. docs/DATA_NODE_SYSTEM.md
 */
import { useState, useEffect, useCallback, useMemo } from 'react'
import {
    Database,
    CheckCircle,
    XCircle,
    Loader2,
    Table2,
    ChevronRight,
    ChevronDown,
    FolderOpen,
    Folder,
    X,
    Settings2,
    Eye,
    Pencil,
} from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'
import {
    databaseAPI,
    sourceNodesAPI,
    type DatabaseTableInfo,
    type DatabaseSchemaInfo,
    type DatabaseColumnInfo,
} from '@/services/api'

type DbType = 'postgresql' | 'mysql' | 'sqlite'

/** Per-column settings (selection + rename) */
interface ColumnSetting {
    name: string
    type: string
    nullable: boolean
    selected: boolean
    alias: string  // empty = use original name
}

/** Per-table settings */
interface TableSettings {
    where: string
    limit: number
    columns: ColumnSetting[]  // empty until loaded
    columnsLoaded: boolean
}

const DEFAULT_LIMIT = 1000

export function DatabaseSourceDialog({
    open,
    onOpenChange,
    initialPosition,
    existingSource,
    mode = 'create',
}: SourceDialogProps) {
    const [dbType, setDbType] = useState<DbType>('postgresql')

    // Connection fields
    const [host, setHost] = useState('localhost')
    const [port, setPort] = useState('5432')
    const [database, setDatabase] = useState('')
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [sqlitePath, setSqlitePath] = useState('')

    // Connection test
    const [isTesting, setIsTesting] = useState(false)
    const [connectionTested, setConnectionTested] = useState(false)
    const [connectionSuccess, setConnectionSuccess] = useState(false)
    const [serverVersion, setServerVersion] = useState('')

    // Schemas (tree)
    const [schemas, setSchemas] = useState<DatabaseSchemaInfo[]>([])
    const [expandedSchemas, setExpandedSchemas] = useState<Set<string>>(new Set())
    const [selectedTableKeys, setSelectedTableKeys] = useState<Set<string>>(new Set())

    // Per-table settings
    const [tableSettingsMap, setTableSettingsMap] = useState<Record<string, TableSettings>>({})

    // Row counts fetched on demand (key → count); -1 = loading
    const [rowCounts, setRowCounts] = useState<Record<string, number>>({})

    // Right panel: preview
    const [activePreviewKey, setActivePreviewKey] = useState<string | null>(null)
    const [previewColumns, setPreviewColumns] = useState<DatabaseColumnInfo[]>([])
    const [previewRows, setPreviewRows] = useState<Record<string, any>[]>([])
    const [previewTotalRows, setPreviewTotalRows] = useState(0)
    const [isLoadingPreview, setIsLoadingPreview] = useState(false)

    // Settings sub-dialog
    const [settingsDialogKey, setSettingsDialogKey] = useState<string | null>(null)
    const [editWhere, setEditWhere] = useState('')
    const [editLimit, setEditLimit] = useState(DEFAULT_LIMIT)
    const [editColumns, setEditColumns] = useState<ColumnSetting[]>([])
    const [isLoadingColumns, setIsLoadingColumns] = useState(false)

    // Global extraction limit
    const [rowLimit, setRowLimit] = useState(DEFAULT_LIMIT)

    // Extraction in progress
    const [isExtracting, setIsExtracting] = useState(false)

    const { isLoading, create, update, boardId } = useSourceDialog({
        sourceType: SourceType.DATABASE,
        onClose: () => {
            resetForm()
            onOpenChange(false)
        },
        position: initialPosition,
    })

    // ---- Helpers ----
    const tKey = (schema: string, table: string) => `${schema}.${table}`

    // ---- Derived data ----
    const allTables = useMemo(() => {
        const flat: DatabaseTableInfo[] = []
        for (const s of schemas) for (const t of s.tables) flat.push(t)
        return flat
    }, [schemas])

    const totalTableCount = allTables.length

    // Selected tables in display order
    const selectedTables = useMemo(
        () => allTables.filter((t) => selectedTableKeys.has(tKey(t.schema_name, t.name))),
        [allTables, selectedTableKeys],
    )

    const getSettings = useCallback(
        (key: string): TableSettings =>
            tableSettingsMap[key] || { where: '', limit: rowLimit, columns: [], columnsLoaded: false },
        [tableSettingsMap, rowLimit],
    )

    const fmtCount = (n: number) => {
        if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
        if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
        return String(n)
    }

    // ---- Build connection params ----
    const connectionParams = useCallback(() => {
        const base: Record<string, any> = { database_type: dbType }
        if (dbType === 'sqlite') {
            base.path = sqlitePath
        } else {
            base.host = host
            base.port = parseInt(port)
            base.database = database
            base.user = username
            base.password = password
        }
        return base
    }, [dbType, host, port, database, username, password, sqlitePath])

    // ---- Edit mode: prefill ----
    useEffect(() => {
        if (mode === 'edit' && existingSource && open) {
            const cfg = existingSource.config || {}
            setDbType(cfg.db_type || 'postgresql')
            setHost(cfg.host || 'localhost')
            setPort(String(cfg.port || (cfg.db_type === 'mysql' ? 3306 : 5432)))
            setDatabase(cfg.database || '')
            setUsername(cfg.username || '')
            setPassword(cfg.password || '')
            setSqlitePath(cfg.path || '')
            setRowLimit(cfg.row_limit || DEFAULT_LIMIT)

            setConnectionTested(true)
            setConnectionSuccess(true)

            // Restore tables
            const tablesFromCfg: DatabaseTableInfo[] = (cfg.tables || []).map((t: any) => ({
                name: t.name,
                schema_name: t.schema || 'public',
                row_count: t.row_count || 0,
                column_count: t.column_count || 0,
            }))
            const schemaMap = new Map<string, DatabaseTableInfo[]>()
            for (const t of tablesFromCfg) {
                if (!schemaMap.has(t.schema_name)) schemaMap.set(t.schema_name, [])
                schemaMap.get(t.schema_name)!.push(t)
            }
            const restored: DatabaseSchemaInfo[] = Array.from(schemaMap.entries()).map(
                ([name, tables]) => ({ name, tables, table_count: tables.length }),
            )
            setSchemas(restored)
            setExpandedSchemas(new Set(restored.map((s) => s.name)))

            const keys = new Set(tablesFromCfg.map((t) => `${t.schema_name}.${t.name}`))
            setSelectedTableKeys(keys)

            // Restore per-table settings
            const settingsRec: Record<string, TableSettings> = {}
            for (const t of cfg.tables || []) {
                const key = `${t.schema || 'public'}.${t.name}`
                settingsRec[key] = {
                    where: t.where || '',
                    limit: t.limit || cfg.row_limit || DEFAULT_LIMIT,
                    columns: (t.columns || []).map((c: any) => ({
                        name: c.name,
                        type: c.type || 'text',
                        nullable: c.nullable ?? true,
                        selected: c.selected ?? true,
                        alias: c.alias || '',
                    })),
                    columnsLoaded: (t.columns || []).length > 0,
                }
            }
            setTableSettingsMap(settingsRec)
        }
    }, [mode, existingSource, open])

    // Fetch exact row count for a table via COUNT(*)
    const fetchRowCount = async (schema: string, table: string) => {
        const key = tKey(schema, table)
        if (rowCounts[key] !== undefined) return // already fetched or loading
        setRowCounts((prev) => ({ ...prev, [key]: -1 })) // -1 = loading
        try {
            const resp = await databaseAPI.preview({
                ...connectionParams(),
                table_name: table,
                schema_name: schema,
                limit: 1, // minimal data, we just need total_rows
            })
            setRowCounts((prev) => ({ ...prev, [key]: resp.data.total_rows }))
        } catch {
            setRowCounts((prev) => ({ ...prev, [key]: 0 }))
        }
    }

    // Fetch row counts for multiple tables at once
    const fetchRowCounts = (tables: { schema: string; table: string }[]) => {
        for (const t of tables) fetchRowCount(t.schema, t.table)
    }

    const resetForm = () => {
        setHost('localhost')
        setPort('5432')
        setDatabase('')
        setUsername('')
        setPassword('')
        setSqlitePath('')
        setConnectionTested(false)
        setConnectionSuccess(false)
        setServerVersion('')
        setSchemas([])
        setExpandedSchemas(new Set())
        setSelectedTableKeys(new Set())
        setTableSettingsMap({})
        setRowCounts({})
        setRowLimit(DEFAULT_LIMIT)
        setActivePreviewKey(null)
        setPreviewColumns([])
        setPreviewRows([])
        setSettingsDialogKey(null)
    }

    const handleDbTypeChange = (value: DbType) => {
        setDbType(value)
        setConnectionTested(false)
        setSchemas([])
        setExpandedSchemas(new Set())
        setSelectedTableKeys(new Set())
        setTableSettingsMap({})
        setRowCounts({})
        setActivePreviewKey(null)
        if (value === 'postgresql') setPort('5432')
        else if (value === 'mysql') setPort('3306')
    }

    // ---- Test connection ----
    const testConnection = async () => {
        setIsTesting(true)
        try {
            const resp = await databaseAPI.testConnection(connectionParams())
            const data = resp.data
            if (data.success) {
                setConnectionTested(true)
                setConnectionSuccess(true)
                setServerVersion(data.server_version || '')
                setSchemas(data.schemas)
                setExpandedSchemas(new Set())
                notify.success(`Подключено — ${data.table_count} таблиц`)
            } else {
                setConnectionTested(true)
                setConnectionSuccess(false)
                notify.error('Не удалось подключиться к БД')
            }
        } catch (error: any) {
            setConnectionTested(true)
            setConnectionSuccess(false)
            notify.error(error.response?.data?.detail || 'Не удалось подключиться к БД')
        } finally {
            setIsTesting(false)
        }
    }

    // ---- Schema tree interactions ----
    const toggleSchema = (name: string) => {
        setExpandedSchemas((p) => {
            const n = new Set(p)
            n.has(name) ? n.delete(name) : n.add(name)
            return n
        })
    }

    const toggleTable = (schema: string, table: string) => {
        const key = tKey(schema, table)
        setSelectedTableKeys((p) => {
            const n = new Set(p)
            if (n.has(key)) {
                n.delete(key)
                // If this was previewed, clear preview
                if (activePreviewKey === key) {
                    setActivePreviewKey(null)
                    setPreviewRows([])
                    setPreviewColumns([])
                }
            } else {
                n.add(key)
                // Fetch row count when table is added
                fetchRowCount(schema, table)
            }
            return n
        })
    }

    const toggleSchemaAll = (schema: DatabaseSchemaInfo) => {
        const keys = schema.tables.map((t) => tKey(schema.name, t.name))
        const allSelected = keys.every((k) => selectedTableKeys.has(k))
        setSelectedTableKeys((p) => {
            const n = new Set(p)
            keys.forEach((k) => allSelected ? n.delete(k) : n.add(k))
            return n
        })
        if (!allSelected) {
            // Fetch row counts for newly added tables
            fetchRowCounts(schema.tables.map((t) => ({ schema: schema.name, table: t.name })))
        }
    }

    const selectAll = () => {
        setSelectedTableKeys(new Set(allTables.map((t) => tKey(t.schema_name, t.name))))
        fetchRowCounts(allTables.map((t) => ({ schema: t.schema_name, table: t.name })))
    }
    const deselectAll = () => {
        setSelectedTableKeys(new Set())
        setActivePreviewKey(null)
        setPreviewRows([])
        setPreviewColumns([])
    }

    // ---- Remove from selection (right panel) ----
    const removeFromSelection = (key: string) => {
        setSelectedTableKeys((p) => {
            const n = new Set(p)
            n.delete(key)
            return n
        })
        if (activePreviewKey === key) {
            setActivePreviewKey(null)
            setPreviewRows([])
            setPreviewColumns([])
        }
    }

    // ---- Preview table ----
    const loadPreview = async (schemaName: string, tableName: string) => {
        const key = tKey(schemaName, tableName)
        if (activePreviewKey === key && previewRows.length > 0) return // already loaded

        setActivePreviewKey(key)
        setIsLoadingPreview(true)
        setPreviewRows([])
        setPreviewColumns([])

        const settings = getSettings(key)

        try {
            const resp = await databaseAPI.preview({
                ...connectionParams(),
                table_name: tableName,
                schema_name: schemaName,
                where_clause: settings.where || undefined,
                limit: Math.min(settings.limit || rowLimit, 50), // preview max 50 rows
            })
            const d = resp.data
            setPreviewColumns(d.columns)
            setPreviewRows(d.rows)
            setPreviewTotalRows(d.total_rows)
        } catch (err: any) {
            notify.error(err.response?.data?.detail || 'Ошибка загрузки предпросмотра')
        } finally {
            setIsLoadingPreview(false)
        }
    }

    // ---- Settings sub-dialog ----
    const openSettingsDialog = async (key: string) => {
        const settings = getSettings(key)
        setEditWhere(settings.where)
        setEditLimit(settings.limit || rowLimit)
        setSettingsDialogKey(key)

        if (settings.columnsLoaded && settings.columns.length > 0) {
            setEditColumns([...settings.columns])
        } else {
            // Load columns from backend
            setIsLoadingColumns(true)
            const [schema, table] = key.split('.')
            try {
                const resp = await databaseAPI.tableColumns({
                    ...connectionParams(),
                    table_name: table,
                    schema_name: schema,
                })
                const cols: ColumnSetting[] = resp.data.columns.map((c) => ({
                    name: c.name,
                    type: c.type,
                    nullable: c.nullable,
                    selected: true,
                    alias: '',
                }))
                setEditColumns(cols)
            } catch (err: any) {
                notify.error('Не удалось загрузить столбцы')
                setEditColumns([])
            } finally {
                setIsLoadingColumns(false)
            }
        }
    }

    const saveSettings = () => {
        if (!settingsDialogKey) return
        setTableSettingsMap((prev) => ({
            ...prev,
            [settingsDialogKey]: {
                where: editWhere,
                limit: editLimit,
                columns: editColumns,
                columnsLoaded: true,
            },
        }))
        // Reset preview if this table is currently previewed
        if (activePreviewKey === settingsDialogKey) {
            setPreviewRows([])
            setPreviewColumns([])
            setActivePreviewKey(null)
        }
        setSettingsDialogKey(null)
    }

    // ---- Submit ----
    const handleSubmit = async () => {
        if (!connectionTested || !connectionSuccess) {
            notify.error('Сначала проверьте подключение')
            return
        }
        if (selectedTableKeys.size === 0) {
            notify.error('Выберите хотя бы одну таблицу')
            return
        }

        const selectedData = allTables.filter((t) => selectedTableKeys.has(tKey(t.schema_name, t.name)))

        const config: Record<string, any> = {
            db_type: dbType,
            row_limit: rowLimit,
            tables: selectedData.map((t) => {
                const key = tKey(t.schema_name, t.name)
                const s = getSettings(key)
                return {
                    name: t.name,
                    schema: t.schema_name,
                    row_count: t.row_count,
                    column_count: t.column_count,
                    limit: s.limit || rowLimit,
                    where: s.where || undefined,
                    columns: s.columnsLoaded
                        ? s.columns.map((c) => ({
                            name: c.name,
                            type: c.type,
                            nullable: c.nullable,
                            selected: c.selected,
                            alias: c.alias || undefined,
                        }))
                        : undefined,
                }
            }),
            host: dbType !== 'sqlite' ? host : undefined,
            port: dbType !== 'sqlite' ? parseInt(port) : undefined,
            database: dbType !== 'sqlite' ? database : undefined,
            username: dbType !== 'sqlite' ? username : undefined,
            password: dbType !== 'sqlite' ? password : undefined,
            path: dbType === 'sqlite' ? sqlitePath : undefined,
        }

        const metadata = {
            name: database || sqlitePath || 'Database',
            server_version: serverVersion,
            table_count: selectedData.length,
        }

        if (mode === 'edit' && existingSource) {
            await update(existingSource.id, config, metadata)
        } else {
            const result = await create(config, metadata)
            if (result.success && result.sourceId && boardId) {
                setIsExtracting(true)
                try {
                    await sourceNodesAPI.extract(boardId, result.sourceId, {
                        position: initialPosition
                            ? { x: initialPosition.x + 300, y: initialPosition.y }
                            : undefined,
                    })
                    notify.success('Данные извлечены из БД')
                } catch (err: any) {
                    notify.error(err.response?.data?.detail || 'Ошибка извлечения данных')
                } finally {
                    setIsExtracting(false)
                }
            }
        }
    }

    const isValid = connectionTested && connectionSuccess && selectedTableKeys.size > 0 && !isExtracting

    const dialogTitle = mode === 'edit'
        ? `Настройки БД — ${existingSource?.metadata?.name || 'источник'}`
        : 'База данных'
    const dialogDescription = mode === 'edit'
        ? 'Изменение параметров подключения и выбора таблиц'
        : 'Подключитесь к PostgreSQL, MySQL или SQLite'

    // ---- Parse schema.table for display ----
    const parseKey = (key: string) => {
        const idx = key.indexOf('.')
        return { schema: key.slice(0, idx), table: key.slice(idx + 1) }
    }

    return (
        <>
            <BaseSourceDialog
                open={open}
                onOpenChange={onOpenChange}
                title={dialogTitle}
                description={dialogDescription}
                icon={<Database className="h-5 w-5 text-orange-500" />}
                isLoading={isLoading || isExtracting}
                isValid={isValid}
                onSubmit={handleSubmit}
                submitLabel={mode === 'edit' ? 'Сохранить' : 'Создать'}
                className="max-w-5xl"
                contentClassName="overflow-hidden"
            >
                <div className="flex gap-3 min-h-[400px]">
                    {/* ==================== LEFT PANEL ==================== */}
                    <div className="w-1/2 flex flex-col gap-2 min-w-0">
                        {/* --- Connection settings --- */}
                        <div className="space-y-2 shrink-0">
                            {/* DB type */}
                            <div className="space-y-1">
                                <Label className="text-xs">Тип СУБД *</Label>
                                <Select value={dbType} onValueChange={(v) => handleDbTypeChange(v as DbType)}>
                                    <SelectTrigger className="h-8 text-xs">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="postgresql">PostgreSQL</SelectItem>
                                        <SelectItem value="mysql">MySQL</SelectItem>
                                        <SelectItem value="sqlite">SQLite</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            {dbType === 'sqlite' ? (
                                <div className="space-y-1">
                                    <Label htmlFor="sqlite-path" className="text-xs">Путь к файлу *</Label>
                                    <Input id="sqlite-path" className="h-8 text-xs" placeholder="/path/to/database.db"
                                        value={sqlitePath}
                                        onChange={(e) => { setSqlitePath(e.target.value); setConnectionTested(false) }}
                                    />
                                </div>
                            ) : (
                                <>
                                    <div className="grid grid-cols-3 gap-2">
                                        <div className="col-span-2 space-y-1">
                                            <Label htmlFor="db-host" className="text-xs">Хост *</Label>
                                            <Input id="db-host" className="h-8 text-xs" value={host}
                                                onChange={(e) => { setHost(e.target.value); setConnectionTested(false) }} />
                                        </div>
                                        <div className="space-y-1">
                                            <Label htmlFor="db-port" className="text-xs">Порт *</Label>
                                            <Input id="db-port" className="h-8 text-xs" value={port}
                                                onChange={(e) => { setPort(e.target.value); setConnectionTested(false) }} />
                                        </div>
                                    </div>
                                    <div className="space-y-1">
                                        <Label htmlFor="db-name" className="text-xs">База данных *</Label>
                                        <Input id="db-name" className="h-8 text-xs" value={database} placeholder="my_database"
                                            onChange={(e) => { setDatabase(e.target.value); setConnectionTested(false) }} />
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="space-y-1">
                                            <Label htmlFor="db-user" className="text-xs">Логин</Label>
                                            <Input id="db-user" className="h-8 text-xs" value={username}
                                                onChange={(e) => { setUsername(e.target.value); setConnectionTested(false) }} />
                                        </div>
                                        <div className="space-y-1">
                                            <Label htmlFor="db-password" className="text-xs">Пароль</Label>
                                            <Input id="db-password" className="h-8 text-xs" type="password" value={password}
                                                onChange={(e) => { setPassword(e.target.value); setConnectionTested(false) }} />
                                        </div>
                                    </div>
                                </>
                            )}

                            {/* Test + status */}
                            <div className="flex items-center gap-2">
                                <Button type="button" variant="outline" size="sm" className="h-7 text-xs"
                                    onClick={testConnection} disabled={isTesting}>
                                    {isTesting && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                                    Подключиться
                                </Button>
                                {connectionTested && (
                                    connectionSuccess ? (
                                        <span className="flex items-center gap-1 text-xs text-green-600">
                                            <CheckCircle className="h-3.5 w-3.5" />
                                            Подключено{serverVersion ? ` · ${serverVersion}` : ''}
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1 text-xs text-red-600">
                                            <XCircle className="h-3.5 w-3.5" /> Ошибка
                                        </span>
                                    )
                                )}
                            </div>
                        </div>

                        {/* --- Schema / Table tree --- */}
                        <div className="flex-1 border rounded-lg flex flex-col min-h-0 overflow-hidden">
                            <div className="flex items-center justify-between px-2.5 py-1.5 border-b bg-muted/30">
                                <span className="text-xs font-medium">
                                    Схемы и таблицы
                                    {totalTableCount > 0 && <span className="text-muted-foreground ml-1">({totalTableCount})</span>}
                                </span>
                                {totalTableCount > 0 && (
                                    <Button type="button" variant="ghost" size="sm" className="h-5 px-1.5 text-[11px]"
                                        onClick={selectedTableKeys.size === totalTableCount ? deselectAll : selectAll}>
                                        {selectedTableKeys.size === totalTableCount ? 'Снять все' : 'Выбрать все'}
                                    </Button>
                                )}
                            </div>
                            <div className="flex-1 overflow-y-auto p-1">
                                {schemas.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                                        <Database className="h-8 w-8 mb-2 opacity-30" />
                                        <span className="text-xs">
                                            {connectionSuccess ? 'Нет доступных таблиц' : 'Подключитесь к базе данных'}
                                        </span>
                                    </div>
                                ) : (
                                    schemas.map((schema) => {
                                        const isExp = expandedSchemas.has(schema.name)
                                        const schemaKeys = schema.tables.map((t) => tKey(schema.name, t.name))
                                        const selCount = schemaKeys.filter((k) => selectedTableKeys.has(k)).length
                                        const allSel = selCount === schema.tables.length && schema.tables.length > 0
                                        return (
                                            <div key={schema.name} className="mb-0.5">
                                                <div className="flex items-center gap-1 px-1.5 py-1 rounded cursor-pointer hover:bg-muted/50"
                                                    onClick={() => toggleSchema(schema.name)}>
                                                    {isExp
                                                        ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                                                        : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
                                                    <Checkbox className="h-3.5 w-3.5" checked={allSel}
                                                        onCheckedChange={() => toggleSchemaAll(schema)}
                                                        onClick={(e) => e.stopPropagation()} />
                                                    {isExp
                                                        ? <FolderOpen className="h-3.5 w-3.5 text-amber-500" />
                                                        : <Folder className="h-3.5 w-3.5 text-amber-500" />}
                                                    <span className="text-xs font-medium flex-1 truncate">{schema.name}</span>
                                                    <span className="text-[11px] text-muted-foreground tabular-nums">
                                                        {selCount > 0 && `${selCount}/`}{schema.table_count}
                                                    </span>
                                                </div>
                                                {isExp && (
                                                    <div className="ml-4">
                                                        {schema.tables.map((table) => {
                                                            const key = tKey(schema.name, table.name)
                                                            const sel = selectedTableKeys.has(key)
                                                            return (
                                                                <div key={key}
                                                                    className={`flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer transition-colors
                                                                        ${sel ? 'bg-blue-50 dark:bg-blue-950/30' : 'hover:bg-muted/40'}`}
                                                                    onClick={() => toggleTable(schema.name, table.name)}>
                                                                    <Checkbox className="h-3.5 w-3.5" checked={sel}
                                                                        onCheckedChange={() => toggleTable(schema.name, table.name)} />
                                                                    <Table2 className="h-3 w-3 text-muted-foreground shrink-0" />
                                                                    <span className="text-xs truncate flex-1">{table.name}</span>
                                                                    <span className="text-[11px] text-muted-foreground tabular-nums shrink-0">
                                                                        {fmtCount(table.row_count)}
                                                                    </span>
                                                                </div>
                                                            )
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )
                                    })
                                )}
                            </div>
                        </div>
                    </div>

                    {/* ==================== RIGHT PANEL ==================== */}
                    <div className="w-1/2 flex flex-col min-w-0 border rounded-lg overflow-hidden">
                        {/* -- Selected tables header -- */}
                        <div className="flex items-center justify-between px-2.5 py-1.5 border-b bg-muted/30 shrink-0">
                            <span className="text-xs font-medium">
                                Выбранные таблицы
                                {selectedTableKeys.size > 0 && (
                                    <span className="text-muted-foreground ml-1">({selectedTableKeys.size})</span>
                                )}
                            </span>
                            <div className="flex items-center gap-1.5">
                                <Label className="text-[11px] text-muted-foreground">Лимит</Label>
                                <Input className="w-16 h-5 text-[11px] px-1.5" type="number" min={1} max={100000}
                                    value={rowLimit}
                                    onChange={(e) => setRowLimit(Math.max(1, parseInt(e.target.value) || DEFAULT_LIMIT))} />
                            </div>
                        </div>

                        {selectedTables.length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground">
                                <Table2 className="h-8 w-8 mb-2 opacity-30" />
                                <span className="text-xs">Выберите таблицы в дереве слева</span>
                            </div>
                        ) : (
                            <>
                                {/* -- Table list (scrollable, compact) -- */}
                                <div className="shrink-0 max-h-[140px] overflow-y-auto border-b">
                                    {selectedTables.map((t) => {
                                        const key = tKey(t.schema_name, t.name)
                                        const isActive = activePreviewKey === key
                                        const settings = getSettings(key)
                                        const hasCustom = settings.where || settings.columnsLoaded
                                        return (
                                            <div
                                                key={key}
                                                className={`flex items-center gap-1.5 px-2.5 py-1.5 cursor-pointer border-b last:border-b-0 transition-colors group
                                                    ${isActive ? 'bg-blue-50 dark:bg-blue-950/30' : 'hover:bg-muted/40'}`}
                                                onClick={() => loadPreview(t.schema_name, t.name)}
                                            >
                                                <Table2 className="h-3 w-3 text-muted-foreground shrink-0" />
                                                <span className="text-xs truncate flex-1 font-medium">
                                                    {t.schema_name !== 'public' && t.schema_name !== 'main' && (
                                                        <span className="text-muted-foreground font-normal">{t.schema_name}.</span>
                                                    )}
                                                    {t.name}
                                                </span>
                                                <span className="text-[11px] text-muted-foreground tabular-nums shrink-0 mr-1">
                                                    {rowCounts[tKey(t.schema_name, t.name)] === -1
                                                        ? <Loader2 className="h-3 w-3 animate-spin inline" />
                                                        : fmtCount(rowCounts[tKey(t.schema_name, t.name)] ?? t.row_count)}
                                                </span>
                                                {hasCustom && (
                                                    <span className="h-1.5 w-1.5 rounded-full bg-blue-400 shrink-0" title="Есть настройки" />
                                                )}
                                                <Button type="button" variant="ghost" size="sm"
                                                    className="h-5 w-5 p-0 opacity-0 group-hover:opacity-100 shrink-0"
                                                    onClick={(e) => { e.stopPropagation(); openSettingsDialog(key) }}
                                                    title="Настройки таблицы">
                                                    <Settings2 className="h-3 w-3" />
                                                </Button>
                                                <Button type="button" variant="ghost" size="sm"
                                                    className="h-5 w-5 p-0 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 shrink-0"
                                                    onClick={(e) => { e.stopPropagation(); removeFromSelection(key) }}
                                                    title="Убрать из выбора">
                                                    <X className="h-3 w-3" />
                                                </Button>
                                            </div>
                                        )
                                    })}
                                </div>

                                {/* -- Preview area -- */}
                                <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
                                    {activePreviewKey ? (
                                        <>
                                            <div className="flex items-center gap-2 px-2.5 py-1 border-b bg-muted/20 shrink-0">
                                                <Eye className="h-3 w-3 text-muted-foreground" />
                                                <span className="text-[11px] text-muted-foreground">
                                                    Предпросмотр: <strong>{parseKey(activePreviewKey).table}</strong>
                                                    {previewTotalRows > 0 && ` (${fmtCount(previewTotalRows)} строк)`}
                                                </span>
                                            </div>
                                            {isLoadingPreview ? (
                                                <div className="flex-1 flex items-center justify-center">
                                                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                                                </div>
                                            ) : previewRows.length > 0 ? (
                                                <div className="flex-1 overflow-auto">
                                                    <table className="w-full text-[11px] border-collapse">
                                                        <thead className="sticky top-0 bg-muted/60 z-10">
                                                            <tr>
                                                                {previewColumns.map((col) => (
                                                                    <th key={col.name}
                                                                        className="px-2 py-1 text-left font-medium border-b whitespace-nowrap">
                                                                        <span>{col.name}</span>
                                                                        <span className="text-muted-foreground font-normal ml-1">
                                                                            {col.type}
                                                                        </span>
                                                                    </th>
                                                                ))}
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {previewRows.map((row, ri) => (
                                                                <tr key={ri} className="border-b hover:bg-muted/20">
                                                                    {previewColumns.map((col) => (
                                                                        <td key={col.name}
                                                                            className="px-2 py-0.5 whitespace-nowrap max-w-[180px] truncate">
                                                                            {row[col.name] === null
                                                                                ? <span className="text-muted-foreground italic">NULL</span>
                                                                                : String(row[col.name])}
                                                                        </td>
                                                                    ))}
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            ) : (
                                                <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">
                                                    Нет данных для отображения
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground">
                                            <Eye className="h-6 w-6 mb-1.5 opacity-30" />
                                            <span className="text-xs">Нажмите на таблицу для предпросмотра</span>
                                        </div>
                                    )}
                                </div>
                            </>
                        )}

                        {/* Extraction progress */}
                        {isExtracting && (
                            <div className="flex items-center gap-2 px-2.5 py-1.5 border-t text-xs text-muted-foreground shrink-0">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Извлечение данных…
                            </div>
                        )}
                    </div>
                </div>
            </BaseSourceDialog>

            {/* ==================== TABLE SETTINGS SUB-DIALOG ==================== */}
            <Dialog open={!!settingsDialogKey} onOpenChange={(v) => !v && setSettingsDialogKey(null)}>
                <DialogContent className="max-w-lg max-h-[80vh] flex flex-col overflow-hidden p-4 gap-3">
                    <DialogHeader className="space-y-0.5">
                        <DialogTitle className="flex items-center gap-2 text-sm">
                            <Settings2 className="h-4 w-4" />
                            Настройки таблицы — {settingsDialogKey ? parseKey(settingsDialogKey).table : ''}
                        </DialogTitle>
                        <DialogDescription className="text-xs">
                            WHERE-фильтр, лимит и выбор столбцов с возможностью переименования
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex-1 overflow-y-auto space-y-3 min-h-0">
                        {/* WHERE clause */}
                        <div className="space-y-1">
                            <Label className="text-xs">WHERE (условие фильтрации)</Label>
                            <Input className="h-8 text-xs font-mono" placeholder='status = 1 AND created_at > "2024-01-01"'
                                value={editWhere} onChange={(e) => setEditWhere(e.target.value)} />
                        </div>

                        {/* Limit */}
                        <div className="space-y-1">
                            <Label className="text-xs">Лимит строк</Label>
                            <Input className="h-8 text-xs w-32" type="number" min={1} max={100000}
                                value={editLimit}
                                onChange={(e) => setEditLimit(Math.max(1, parseInt(e.target.value) || DEFAULT_LIMIT))} />
                        </div>

                        {/* Columns */}
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between">
                                <Label className="text-xs">Столбцы</Label>
                                {editColumns.length > 0 && (
                                    <Button type="button" variant="ghost" size="sm" className="h-5 px-1.5 text-[11px]"
                                        onClick={() => {
                                            const allSelected = editColumns.every((c) => c.selected)
                                            setEditColumns(editColumns.map((c) => ({ ...c, selected: !allSelected })))
                                        }}>
                                        {editColumns.every((c) => c.selected) ? 'Снять все' : 'Выбрать все'}
                                    </Button>
                                )}
                            </div>

                            {isLoadingColumns ? (
                                <div className="flex items-center gap-2 py-4 justify-center text-xs text-muted-foreground">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Загрузка столбцов…
                                </div>
                            ) : editColumns.length === 0 ? (
                                <div className="text-xs text-muted-foreground py-2 text-center">
                                    Столбцы не найдены
                                </div>
                            ) : (
                                <div className="border rounded max-h-[220px] overflow-y-auto">
                                    {editColumns.map((col, idx) => (
                                        <div key={col.name}
                                            className={`flex items-center gap-2 px-2.5 py-1.5 border-b last:border-b-0
                                                ${col.selected ? '' : 'opacity-50'}`}>
                                            <Checkbox className="h-3.5 w-3.5 shrink-0" checked={col.selected}
                                                onCheckedChange={(v) => {
                                                    const next = [...editColumns]
                                                    next[idx] = { ...next[idx], selected: !!v }
                                                    setEditColumns(next)
                                                }} />
                                            <span className="text-xs w-[120px] shrink-0 truncate font-mono" title={col.name}>
                                                {col.name}
                                            </span>
                                            <span className="text-[11px] text-muted-foreground w-[60px] shrink-0 truncate">
                                                {col.type}
                                            </span>
                                            <div className="flex items-center gap-1 flex-1 min-w-0">
                                                <Pencil className="h-3 w-3 text-muted-foreground shrink-0" />
                                                <Input className="h-6 text-xs flex-1 min-w-0"
                                                    placeholder={col.name}
                                                    value={col.alias}
                                                    onChange={(e) => {
                                                        const next = [...editColumns]
                                                        next[idx] = { ...next[idx], alias: e.target.value }
                                                        setEditColumns(next)
                                                    }}
                                                    disabled={!col.selected}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    <DialogFooter className="pt-1">
                        <Button size="sm" variant="outline" onClick={() => setSettingsDialogKey(null)}>
                            Отмена
                        </Button>
                        <Button size="sm" onClick={saveSettings}>
                            Применить
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    )
}
