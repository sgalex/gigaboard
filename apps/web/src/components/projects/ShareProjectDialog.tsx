import { useEffect, useState } from 'react'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { projectsAPI, usersAPI } from '@/services/api'
import { notify } from '@/store/notificationStore'
import type { ProjectCollaboratorEntry, UserSearchResult } from '@/types'
import { Loader2, Search, Share2, Trash2, UserPlus, Users } from 'lucide-react'
import { cn } from '@/lib/utils'

const ROLE_LABEL: Record<string, string> = {
    owner: 'Владелец',
    viewer: 'Просмотр',
    editor: 'Изменение',
    admin: 'Полный доступ',
}

type ShareProjectDialogProps = {
    open: boolean
    onOpenChange: (open: boolean) => void
    projectId: string
    projectName: string
    canManage: boolean
}

/** Новые приглашения всегда с ролью viewer; сменить роль можно в списке ниже. */
const DEFAULT_INVITE_ROLE = 'viewer' as const

export function ShareProjectDialog({
    open,
    onOpenChange,
    projectId,
    projectName,
    canManage,
}: ShareProjectDialogProps) {
    const [collaborators, setCollaborators] = useState<ProjectCollaboratorEntry[]>([])
    const [loading, setLoading] = useState(false)
    const [search, setSearch] = useState('')
    const [searching, setSearching] = useState(false)
    const [searchHits, setSearchHits] = useState<UserSearchResult[]>([])

    useEffect(() => {
        if (!open) return
        let cancelled = false
        ;(async () => {
            setLoading(true)
            try {
                const r = await projectsAPI.listCollaborators(projectId)
                if (!cancelled) setCollaborators(r.data)
            } catch {
                if (!cancelled) setCollaborators([])
                notify.error('Не удалось загрузить список участников', { title: 'Ошибка' })
            } finally {
                if (!cancelled) setLoading(false)
            }
        })()
        setSearch('')
        setSearchHits([])
        return () => {
            cancelled = true
        }
    }, [open, projectId])

    useEffect(() => {
        const q = search.trim()
        if (q.length < 2) {
            setSearchHits([])
            return
        }
        const t = window.setTimeout(() => {
            ;(async () => {
                setSearching(true)
                try {
                    const r = await usersAPI.search(q, projectId)
                    const collabIds = new Set(collaborators.map((c) => c.user_id))
                    setSearchHits(r.data.filter((u) => !collabIds.has(u.id)))
                } catch {
                    setSearchHits([])
                } finally {
                    setSearching(false)
                }
            })()
        }, 320)
        return () => window.clearTimeout(t)
    }, [search, collaborators, projectId])

    const addUser = async (u: UserSearchResult) => {
        if (!canManage) return
        try {
            await projectsAPI.addCollaborator(projectId, u.id, DEFAULT_INVITE_ROLE)
            notify.success(`Добавлен: ${u.username}`, { title: 'Доступ' })
            setCollaborators((prev) => [
                ...prev,
                {
                    user_id: u.id,
                    username: u.username,
                    email: u.email,
                    role: DEFAULT_INVITE_ROLE,
                    created_at: new Date().toISOString(),
                },
            ])
            setSearch('')
            setSearchHits([])
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                'Не удалось добавить пользователя'
            notify.error(typeof msg === 'string' ? msg : 'Ошибка', { title: 'Доступ' })
        }
    }

    const removeUser = async (userId: string) => {
        if (!canManage) return
        try {
            await projectsAPI.removeCollaborator(projectId, userId)
            notify.success('Доступ отозван', { title: 'Готово' })
            setCollaborators((prev) => prev.filter((c) => c.user_id !== userId))
        } catch {
            notify.error('Не удалось убрать участника', { title: 'Ошибка' })
        }
    }

    const changeRole = async (userId: string, newRole: string) => {
        if (!canManage) return
        try {
            await projectsAPI.updateCollaboratorRole(projectId, userId, newRole)
            setCollaborators((prev) =>
                prev.map((c) => (c.user_id === userId ? { ...c, role: newRole } : c))
            )
            notify.success('Роль обновлена', { title: 'Готово' })
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                'Не удалось изменить роль'
            notify.error(typeof msg === 'string' ? msg : 'Ошибка', { title: 'Доступ' })
        }
    }

    const searchQueryOk = search.trim().length >= 2
    const nonOwnerCount = collaborators.filter((c) => c.role !== 'owner').length

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className={cn(
                    'flex h-[min(560px,90vh)] max-h-[90vh] w-full max-w-2xl flex-col gap-0 overflow-hidden p-0',
                    'border-0 shadow-2xl sm:rounded-2xl',
                    'bg-gradient-to-b from-card to-background'
                )}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Шапка */}
                <div className="relative shrink-0 border-b border-border/60 bg-gradient-to-r from-primary/[0.12] via-primary/[0.06] to-transparent px-6 pb-4 pt-5">
                    <div
                        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_0%_-20%,hsl(var(--primary)/0.15),transparent)]"
                        aria-hidden
                    />
                    <DialogHeader className="relative space-y-3 text-left">
                        <div className="flex gap-4">
                            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/15 text-primary shadow-inner ring-1 ring-primary/20">
                                <Share2 className="h-6 w-6" strokeWidth={1.75} />
                            </div>
                            <div className="min-w-0 flex-1 space-y-1.5 pt-0.5">
                                <DialogTitle className="text-xl font-semibold tracking-tight sm:text-2xl">
                                    Совместный доступ
                                </DialogTitle>
                                <DialogDescription className="text-[15px] leading-relaxed text-muted-foreground">
                                    Проект{' '}
                                    <span className="font-medium text-foreground">«{projectName}»</span>.
                                    {canManage
                                        ? ' Новые участники получают доступ «Просмотр»; роль можно изменить в списке ниже. Владельца нельзя исключить или понизить.'
                                        : ' Вы можете просматривать список участников. Приглашать и менять роли могут только владелец и участники с полным доступом.'}
                                </DialogDescription>
                            </div>
                        </div>
                    </DialogHeader>
                </div>

                <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden px-6 pb-5 pt-3">
                    {!canManage && (
                        <div className="shrink-0 rounded-xl border border-dashed border-border/70 bg-muted/20 px-3 py-3 text-center text-sm leading-relaxed text-muted-foreground">
                            Приглашать и менять роли могут только владелец и участники с{' '}
                            <span className="font-medium text-foreground">полным доступом</span>.
                            Ниже — текущий список.
                        </div>
                    )}
                    {canManage && (
                        <section className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
                            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                                <Search className="h-4 w-4 shrink-0 text-primary/80" />
                                Найти пользователя
                            </div>
                            <div className="relative shrink-0">
                                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    className="h-10 rounded-xl border-border/80 bg-background/80 pl-10 pr-4 text-base shadow-sm transition-shadow focus-visible:ring-primary/30"
                                    placeholder="Имя или email (от 2 символов)…"
                                    value={search}
                                    onChange={(e) => setSearch(e.target.value)}
                                    autoComplete="off"
                                    spellCheck={false}
                                />
                            </div>
                            <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border/80 bg-muted/25 shadow-sm">
                                {searching ? (
                                    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 overflow-hidden px-4 py-6 text-sm text-muted-foreground">
                                        <Loader2 className="h-7 w-7 shrink-0 animate-spin text-primary/70" />
                                        <span>Ищем пользователей…</span>
                                    </div>
                                ) : !searchQueryOk ? (
                                    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 overflow-hidden px-4 py-6 text-center text-sm text-muted-foreground">
                                        <div className="rounded-full bg-muted/80 p-2.5">
                                            <Search className="h-5 w-5 opacity-50" />
                                        </div>
                                        <p>Введите минимум два символа, чтобы начать поиск.</p>
                                    </div>
                                ) : searchHits.length === 0 ? (
                                    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 overflow-hidden px-4 py-6 text-center text-sm text-muted-foreground">
                                        <p>Никого не нашли — попробуйте другой запрос.</p>
                                    </div>
                                ) : (
                                    <ul className="min-h-0 flex-1 list-none overflow-y-auto overscroll-contain p-1">
                                        {searchHits.map((u) => (
                                            <li
                                                key={u.id}
                                                className="flex items-center justify-between gap-3 border-b border-border/50 px-3 py-2.5 last:border-0"
                                            >
                                                <div className="min-w-0 flex-1">
                                                    <div className="truncate font-medium text-foreground">
                                                        {u.username}
                                                    </div>
                                                    <div className="truncate text-xs text-muted-foreground">
                                                        {u.email}
                                                    </div>
                                                </div>
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    className="shrink-0 rounded-lg"
                                                    onClick={() => addUser(u)}
                                                >
                                                    <UserPlus className="mr-1.5 h-3.5 w-3.5" />
                                                    Добавить
                                                </Button>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        </section>
                    )}

                    <section className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
                        <div className="flex shrink-0 items-center justify-between gap-2">
                            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                                <Users className="h-4 w-4 text-primary/80" />
                                Участники
                                {!loading && (
                                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                                        {collaborators.length}
                                    </span>
                                )}
                                {!loading && nonOwnerCount === 0 && collaborators.length > 0 && (
                                    <span className="text-xs font-normal text-muted-foreground">
                                        (только владелец)
                                    </span>
                                )}
                            </div>
                        </div>

                        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border/80 bg-muted/20 shadow-sm">
                            {loading ? (
                                <div className="flex min-h-0 flex-1 flex-col justify-center gap-2 p-3">
                                    {[1, 2, 3].map((i) => (
                                        <div
                                            key={i}
                                            className="flex animate-pulse items-center gap-3 rounded-lg bg-muted/60 px-3 py-2.5"
                                        >
                                            <div className="h-9 w-9 shrink-0 rounded-full bg-muted" />
                                            <div className="min-w-0 flex-1 space-y-2">
                                                <div className="h-3.5 w-2/5 rounded bg-muted" />
                                                <div className="h-2.5 w-3/5 rounded bg-muted/80" />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : collaborators.length === 0 ? (
                                <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 px-4 py-6 text-center">
                                    <div className="rounded-2xl bg-muted/50 p-3 ring-1 ring-border/50">
                                        <Users className="h-8 w-8 text-muted-foreground/60" strokeWidth={1.25} />
                                    </div>
                                    <div className="space-y-1">
                                        <p className="font-medium text-foreground">Нет данных</p>
                                        <p className="max-w-xs text-sm text-muted-foreground">
                                            Не удалось загрузить список участников.
                                        </p>
                                    </div>
                                </div>
                            ) : (
                                <ul className="min-h-0 flex-1 list-none overflow-y-auto overflow-x-hidden overscroll-contain p-1.5">
                                    {collaborators.map((c) => (
                                        <li
                                            key={c.user_id}
                                            className="mb-1 flex items-center justify-between gap-3 rounded-lg border border-transparent bg-background/60 px-3 py-2.5 last:mb-0 hover:border-border/60 hover:bg-background/90"
                                        >
                                            <div className="flex min-w-0 flex-1 items-center gap-3">
                                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                                                    {c.username.slice(0, 1).toUpperCase()}
                                                </div>
                                                <div className="min-w-0">
                                                    <div className="truncate font-medium">{c.username}</div>
                                                    <div className="truncate text-xs text-muted-foreground">
                                                        {c.email}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex shrink-0 items-center gap-2">
                                                {c.role === 'owner' ? (
                                                    <Badge variant="secondary" className="font-normal">
                                                        {ROLE_LABEL.owner}
                                                    </Badge>
                                                ) : canManage ? (
                                                    <>
                                                        <Select
                                                            value={c.role}
                                                            onValueChange={(v) => changeRole(c.user_id, v)}
                                                        >
                                                            <SelectTrigger className="h-8 w-[148px] rounded-lg text-xs">
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                <SelectItem value="viewer">
                                                                    {ROLE_LABEL.viewer}
                                                                </SelectItem>
                                                                <SelectItem value="editor">
                                                                    {ROLE_LABEL.editor}
                                                                </SelectItem>
                                                                <SelectItem value="admin">
                                                                    {ROLE_LABEL.admin}
                                                                </SelectItem>
                                                            </SelectContent>
                                                        </Select>
                                                        <Button
                                                            type="button"
                                                            size="icon"
                                                            variant="ghost"
                                                            className="h-9 w-9 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                                                            title="Убрать доступ"
                                                            onClick={() => removeUser(c.user_id)}
                                                        >
                                                            <Trash2 className="h-4 w-4" />
                                                        </Button>
                                                    </>
                                                ) : (
                                                    <Badge variant="outline" className="font-normal">
                                                        {ROLE_LABEL[c.role] ?? c.role}
                                                    </Badge>
                                                )}
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    </section>
                </div>
            </DialogContent>
        </Dialog>
    )
}
