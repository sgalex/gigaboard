import { useState } from 'react'
import { AppLayout } from '@/components/layout/AppLayout'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuthStore } from '@/store/authStore'
import { User, Settings2, Workflow, Sparkles } from 'lucide-react'
import { SystemLLMSettingsPanel } from '@/components/settings/SystemLLMSettingsPanel'
import { MultiAgentUserSettingsPanel } from '@/components/settings/MultiAgentUserSettingsPanel'
import { MultiAgentPlaygroundPanel } from '@/components/settings/MultiAgentPlaygroundPanel'

export function UserProfilePage() {
    const { user } = useAuthStore()
    const isAdmin = user?.role === 'admin'
    const [activeTab, setActiveTab] = useState('general')

    return (
        <AppLayout showExplorer={false}>
            <div className="max-w-4xl mx-auto py-8 px-4">
                <header className="mb-6 space-y-1">
                    <h1 className="text-2xl font-bold tracking-tight">Настройки</h1>
                    <p className="text-sm text-muted-foreground">
                        Профиль и параметры системы. Разделы Multi-Agent, LLM и Playground — только для
                        администратора.
                    </p>
                </header>

                <Tabs
                    value={activeTab}
                    onValueChange={setActiveTab}
                    orientation="vertical"
                    className="flex flex-col sm:flex-row sm:items-start gap-6"
                >
                    <TabsList className="flex h-auto flex-col items-stretch rounded-lg border border-border bg-muted/30 p-1 w-full sm:w-48 shrink-0">
                        <TabsTrigger
                            value="general"
                            className="w-full justify-start gap-2 text-left data-[state=active]:bg-background data-[state=active]:shadow-sm"
                        >
                            <User className="h-4 w-4 shrink-0" />
                            Общие
                        </TabsTrigger>
                        {isAdmin && (
                            <>
                                <TabsTrigger
                                    value="multi-agent"
                                    className="w-full justify-start gap-2 text-left data-[state=active]:bg-background data-[state=active]:shadow-sm"
                                >
                                    <Workflow className="h-4 w-4 shrink-0" />
                                    Multi-Agent
                                </TabsTrigger>
                                <TabsTrigger
                                    value="llm"
                                    className="w-full justify-start gap-2 text-left data-[state=active]:bg-background data-[state=active]:shadow-sm"
                                >
                                    <Settings2 className="h-4 w-4 shrink-0" />
                                    Настройки LLM
                                </TabsTrigger>
                                <TabsTrigger
                                    value="playground"
                                    className="w-full justify-start gap-2 text-left data-[state=active]:bg-background data-[state=active]:shadow-sm"
                                >
                                    <Sparkles className="h-4 w-4 shrink-0" />
                                    Playground
                                </TabsTrigger>
                            </>
                        )}
                    </TabsList>

                    <div className="flex-1 min-w-0">
                        <TabsContent value="general" className="mt-0">
                            <section className="rounded-lg border border-border bg-card p-6 space-y-4">
                                <h2 className="text-lg font-semibold">Общие данные</h2>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>Email</Label>
                                        <Input value={user?.email ?? ''} disabled />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Имя пользователя</Label>
                                        <Input value={user?.username ?? ''} disabled />
                                    </div>
                                </div>
                            </section>
                        </TabsContent>

                        {isAdmin && (
                            <>
                                <TabsContent value="multi-agent" className="mt-0">
                                    <section className="rounded-lg border border-border bg-card p-6">
                                        <MultiAgentUserSettingsPanel />
                                    </section>
                                </TabsContent>
                                <TabsContent value="llm" className="mt-0">
                                    <section className="rounded-lg border border-border bg-card p-6">
                                        <SystemLLMSettingsPanel />
                                    </section>
                                </TabsContent>
                                <TabsContent value="playground" className="mt-0">
                                    <section className="rounded-lg border border-border bg-card p-6">
                                        <MultiAgentPlaygroundPanel />
                                    </section>
                                </TabsContent>
                            </>
                        )}
                    </div>
                </Tabs>

                {!isAdmin && (
                    <p className="mt-4 text-sm text-muted-foreground">
                        Параметры Multi-Agent, LLM и Playground настраивает администратор системы.
                    </p>
                )}
            </div>
        </AppLayout>
    )
}

