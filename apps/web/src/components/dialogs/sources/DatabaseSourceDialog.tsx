/**
 * Database Source Dialog - диалог для подключения к БД.
 */
import { useState } from 'react'
import { Database, CheckCircle, XCircle, Loader2 } from 'lucide-react'
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
import { SourceType } from '@/types'
import { notify } from '@/store/notificationStore'
import { BaseSourceDialog } from './BaseSourceDialog'
import { useSourceDialog } from './useSourceDialog'
import { SourceDialogProps } from './types'

type DbType = 'postgresql' | 'mysql' | 'sqlite'

export function DatabaseSourceDialog({ open, onOpenChange, initialPosition }: SourceDialogProps) {
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

    // Tables
    const [availableTables, setAvailableTables] = useState<string[]>([])
    const [selectedTables, setSelectedTables] = useState<string[]>([])

    const { isLoading, create } = useSourceDialog({
        sourceType: SourceType.DATABASE,
        onClose: () => {
            resetForm()
            onOpenChange(false)
        },
        position: initialPosition,
    })

    const resetForm = () => {
        setHost('localhost')
        setPort('5432')
        setDatabase('')
        setUsername('')
        setPassword('')
        setSqlitePath('')
        setConnectionTested(false)
        setAvailableTables([])
        setSelectedTables([])
    }

    const handleDbTypeChange = (value: DbType) => {
        setDbType(value)
        setConnectionTested(false)
        setAvailableTables([])
        setSelectedTables([])

        // Set default port
        if (value === 'postgresql') setPort('5432')
        else if (value === 'mysql') setPort('3306')
    }

    const testConnection = async () => {
        setIsTesting(true)
        try {
            // TODO: Call backend API to test connection
            // For now, simulate success
            await new Promise(resolve => setTimeout(resolve, 1000))

            setConnectionTested(true)
            setConnectionSuccess(true)
            setAvailableTables(['users', 'orders', 'products', 'categories'])
            notify.success('Подключение успешно')
        } catch (error) {
            setConnectionTested(true)
            setConnectionSuccess(false)
            notify.error('Не удалось подключиться к БД')
        } finally {
            setIsTesting(false)
        }
    }

    const handleSubmit = async () => {
        if (!connectionTested || !connectionSuccess) {
            notify.error('Сначала проверьте подключение')
            return
        }

        if (selectedTables.length === 0) {
            notify.error('Выберите хотя бы одну таблицу')
            return
        }

        const config: Record<string, any> = {
            db_type: dbType,
            tables: selectedTables.map(name => ({ name, limit: 1000 })),
        }

        if (dbType === 'sqlite') {
            config.path = sqlitePath
        } else {
            config.host = host
            config.port = parseInt(port)
            config.database = database
            config.username = username
            config.password = password
        }

        await create(config, { name: database || sqlitePath })
    }

    const isValid = connectionTested && connectionSuccess && selectedTables.length > 0

    return (
        <BaseSourceDialog
            open={open}
            onOpenChange={onOpenChange}
            title="База данных"
            description="Подключитесь к PostgreSQL, MySQL или SQLite"
            icon={<Database className="h-5 w-5 text-orange-500" />}
            isLoading={isLoading}
            isValid={isValid}
            onSubmit={handleSubmit}
        >
            <div className="space-y-4">
                <div className="space-y-2">
                    <Label>Тип СУБД *</Label>
                    <Select value={dbType} onValueChange={handleDbTypeChange}>
                        <SelectTrigger>
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
                    <div className="space-y-2">
                        <Label htmlFor="sqlite-path">Путь к файлу *</Label>
                        <Input
                            id="sqlite-path"
                            placeholder="/path/to/database.db"
                            value={sqlitePath}
                            onChange={(e) => {
                                setSqlitePath(e.target.value)
                                setConnectionTested(false)
                            }}
                        />
                    </div>
                ) : (
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="db-host">Хост *</Label>
                            <Input
                                id="db-host"
                                value={host}
                                onChange={(e) => {
                                    setHost(e.target.value)
                                    setConnectionTested(false)
                                }}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="db-port">Порт *</Label>
                            <Input
                                id="db-port"
                                value={port}
                                onChange={(e) => {
                                    setPort(e.target.value)
                                    setConnectionTested(false)
                                }}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="db-name">База данных *</Label>
                            <Input
                                id="db-name"
                                value={database}
                                onChange={(e) => {
                                    setDatabase(e.target.value)
                                    setConnectionTested(false)
                                }}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="db-user">Пользователь</Label>
                            <Input
                                id="db-user"
                                value={username}
                                onChange={(e) => {
                                    setUsername(e.target.value)
                                    setConnectionTested(false)
                                }}
                            />
                        </div>
                        <div className="col-span-2 space-y-2">
                            <Label htmlFor="db-password">Пароль</Label>
                            <Input
                                id="db-password"
                                type="password"
                                value={password}
                                onChange={(e) => {
                                    setPassword(e.target.value)
                                    setConnectionTested(false)
                                }}
                            />
                        </div>
                    </div>
                )}

                {/* Test Connection Button */}
                <div className="flex items-center gap-4">
                    <Button
                        type="button"
                        variant="outline"
                        onClick={testConnection}
                        disabled={isTesting}
                    >
                        {isTesting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Проверить подключение
                    </Button>

                    {connectionTested && (
                        <div className="flex items-center gap-2">
                            {connectionSuccess ? (
                                <>
                                    <CheckCircle className="h-5 w-5 text-green-500" />
                                    <span className="text-sm text-green-600">Подключено</span>
                                </>
                            ) : (
                                <>
                                    <XCircle className="h-5 w-5 text-red-500" />
                                    <span className="text-sm text-red-600">Ошибка</span>
                                </>
                            )}
                        </div>
                    )}
                </div>

                {/* Tables Selection */}
                {availableTables.length > 0 && (
                    <div className="space-y-2 border rounded-lg p-4">
                        <Label>Выберите таблицы *</Label>
                        <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto">
                            {availableTables.map((table) => (
                                <div key={table} className="flex items-center space-x-2">
                                    <Checkbox
                                        id={`table-${table}`}
                                        checked={selectedTables.includes(table)}
                                        onCheckedChange={(checked: boolean) => {
                                            if (checked) {
                                                setSelectedTables([...selectedTables, table])
                                            } else {
                                                setSelectedTables(selectedTables.filter(t => t !== table))
                                            }
                                        }}
                                    />
                                    <label
                                        htmlFor={`table-${table}`}
                                        className="text-sm cursor-pointer"
                                    >
                                        {table}
                                    </label>
                                </div>
                            ))}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Выбрано: {selectedTables.length} из {availableTables.length}
                        </p>
                    </div>
                )}
            </div>
        </BaseSourceDialog>
    )
}
