import { Link } from 'react-router-dom'
import { useEffect } from 'react'
import {
    Layout,
    Sparkles,
    Users,
    Link2,
    Bot,
    BarChart3,
    Table,
    Gauge,
    Code2,
    Shield,
    Clock,
    Key,
    FileText,
    Zap,
    Brain,
    Search,
    PieChart,
    Terminal,
    FileOutput,
    FormInput,
    Globe,
    RefreshCw,
    CheckCircle2,
    ArrowRight,
    Star,
    Quote,
    Mic,
    Calendar,
    Share2,
    MessageSquare,
    MousePointerClick,
    GitBranch,
    Download,
    Languages,
    Wand2,
    Target,
    Lightbulb,
    LayoutGrid,
    LayoutDashboard,
    Database,
    Eye,
    AlertTriangle,
    Workflow,
    FileCode,
    Network,
    Boxes,
    PlayCircle,
    Radio,
    Layers,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

// Hero Section
const HeroSection = () => (
    <section className="relative overflow-hidden bg-black px-6 py-32 sm:py-40 lg:py-48">
        {/* Hero Background Illustration - fills entire section */}
        <div className="absolute inset-0 z-0">
            <img
                src="/images/landing/hero-background.jpg"
                alt="AI Data Analytics Background"
                width="2400"
                height="1200"
                className="absolute inset-0 h-full w-full object-cover opacity-50"
            />
            {/* Vignette overlay for better text contrast */}
            <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/40 to-black/80" />
            <div className="absolute inset-0 bg-gradient-to-r from-black/50 via-transparent to-black/50" />
        </div>

        {/* Content - no background card, direct on image */}
        <div className="relative z-10 mx-auto max-w-6xl text-center">
            {/* Badge */}
            <div className="mb-12 flex justify-center">
                <div className="inline-flex items-center gap-2 rounded-full border border-[#21A038] bg-[#21A038]/20 px-6 py-2.5 text-sm font-medium text-[#21A038] backdrop-blur-sm">
                    <Sparkles className="h-4 w-4" />
                    AI-Powered Data Analytics Platform
                    <Sparkles className="h-4 w-4" />
                </div>
            </div>

            {/* Heading */}
            <h1 className="mb-6 text-6xl font-bold tracking-tight text-white sm:text-7xl lg:text-8xl">
                От вопроса к инсайту
            </h1>
            <div className="mb-10">
                <span className="inline-block text-5xl sm:text-6xl lg:text-7xl font-extrabold text-[#21A038]">
                    одним промптом
                </span>
            </div>

            {/* Description */}
            <p className="mx-auto max-w-3xl text-xl leading-relaxed text-gray-200 sm:text-2xl mb-14">
                <strong className="text-white">GigaBoard</strong> — платформа для создания аналитических досок и data-driven дашбордов силой AI.
                Задайте вопрос на естественном языке, AI построит полный анализ с визуализациями за минуты.
            </p>

            {/* Buttons */}
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row mb-16">
                <Link to="/register">
                    <Button size="lg" className="gap-2 bg-[#21A038] px-12 py-7 text-lg font-semibold text-white transition-all duration-300 hover:bg-[#1a8030] hover:scale-105 shadow-2xl shadow-[#21A038]/40">
                        Начать бесплатно
                        <ArrowRight className="h-5 w-5" />
                    </Button>
                </Link>
                <Link to="/login">
                    <Button variant="outline" size="lg" className="gap-2 border-2 border-white/60 bg-white/5 px-12 py-7 text-lg font-semibold text-white backdrop-blur-sm transition-all duration-300 hover:bg-white/15 hover:scale-105">
                        Войти в аккаунт
                    </Button>
                </Link>
            </div>

            {/* Feature highlights */}
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-3 mx-auto max-w-4xl">
                {[
                    { icon: Zap, text: 'No-Code Analytics' },
                    { icon: Bot, text: 'AI-Powered Insights' },
                    { icon: Clock, text: 'Результат за минуты' },
                ].map(({ icon: Icon, text }) => (
                    <div key={text} className="flex items-center justify-center gap-3 rounded-xl border border-white/20 bg-white/5 p-5 backdrop-blur-sm transition-all duration-300 hover:bg-white/10 hover:border-white/40">
                        <Icon className="h-5 w-5 text-[#21A038]" />
                        <span className="font-medium text-white">{text}</span>
                    </div>
                ))}
            </div>
        </div>
    </section>
)

// Core Features Section — Professional Features
const CoreFeaturesSection = () => {
    const features = [
        {
            icon: MessageSquare,
            title: 'Natural Language Interface',
            description: 'Формулируйте запросы на естественном языке: "Проанализируй динамику продаж" или "Сравни конверсию по каналам". AI интерпретирует контекст и выполняет анализ.',
            details: ['Естественный язык', 'Понимает контекст', 'Учится на ваших вопросах', 'Даёт рекомендации'],
            color: 'bg-[#21A038]/10 text-[#21A038]',
        },
        {
            icon: Database,
            title: 'Automated Data Pipeline',
            description: 'AI автоматически строит data pipeline: подключается к источникам, извлекает и трансформирует данные, создаёт агрегации — от сырых данных до готовых метрик.',
            details: ['Файлы любых форматов', 'Базы данных', 'Облачные сервисы', 'Публичные датасеты'],
            color: 'bg-purple-500/10 text-purple-500',
        },
        {
            icon: Sparkles,
            title: 'Smart Visualization',
            description: 'AI анализирует данные и выбирает оптимальные типы визуализаций (charts, tables, KPI cards). Создаёт dashboard-ready виджеты с правильной агрегацией.',
            details: ['Графики и диаграммы', 'Таблицы и карточки', 'Интерактивные элементы', 'Готово к презентации'],
            color: 'bg-[#21A038]/10 text-[#21A038]',
        },
        {
            icon: Users,
            title: 'Real-Time Collaboration',
            description: 'Работайте над аналитикой совместно: real-time updates, комментарии к данным, shared boards. Обсуждайте инсайты с командой в контексте дашборда.',
            details: ['Совместное редактирование', 'Комментарии и обсуждения', 'Общий доступ', 'История изменений'],
            color: 'bg-[#21A038]/10 text-[#21A038]',
        },
    ]

    return (
        <section id="features" className="px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Всё, что вам нужно
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
                        Простые инструменты для сложных задач — никаких технических знаний не требуется
                    </p>
                </div>

                <div className="mt-16 grid gap-8 lg:grid-cols-2">
                    {features.map((feature) => (
                        <Card key={feature.title} className="group relative overflow-hidden border-2 border-border/60 bg-gradient-to-br from-card via-card to-card/80 backdrop-blur-sm transition-all duration-500 hover:scale-[1.03] hover:border-primary/70 hover:shadow-2xl hover:shadow-primary/20 hover:backdrop-blur-md">
                            {/* Enhanced gradient overlay on hover */}
                            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-accent/5 to-primary/5 opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
                            {/* Shimmer effect */}
                            <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent opacity-0 transition-all duration-1000 group-hover:translate-x-full group-hover:opacity-100" />

                            <CardHeader className="relative">
                                <div className={`mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl ${feature.color} shadow-2xl transition-all duration-500 group-hover:scale-125 group-hover:shadow-2xl group-hover:rotate-6`}>
                                    <feature.icon className="h-8 w-8 transition-transform duration-500 group-hover:scale-110" />
                                </div>
                                <CardTitle className="text-2xl">{feature.title}</CardTitle>
                                <CardDescription className="text-base leading-relaxed">
                                    {feature.description}
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="relative">
                                <ul className="grid grid-cols-2 gap-3">
                                    {feature.details.map((detail) => (
                                        <li key={detail} className="flex items-center gap-2 text-sm text-muted-foreground transition-colors group-hover:text-foreground">
                                            <CheckCircle2 className="h-4 w-4 shrink-0 text-success transition-transform group-hover:scale-110" />
                                            {detail}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </section>
    )
}

// Benefits Section — Why GigaBoard
const BenefitsSection = () => {
    const benefits = [
        { name: 'Time to Insight', desc: 'От вопроса до dashboard за минуты, не часы', color: '#21A038', icon: Clock },
        { name: 'Self-Service Analytics', desc: 'Не зависите от Data Team для каждого отчёта', color: '#21A038', icon: Zap },
        { name: 'Live Data Updates', desc: 'Real-time обновление метрик и визуализаций', color: '#21A038', icon: RefreshCw },
        { name: 'Production-Ready', desc: 'Dashboard-quality визуализации из коробки', color: '#21A038', icon: Eye },
        { name: 'Cross-Platform', desc: 'Десктоп, планшет, мобильный — везде работает', color: '#21A038', icon: Globe },
        { name: 'Enterprise Security', desc: 'Role-based access, audit logs, encryption', color: '#21A038', icon: Shield },
    ]

    return (
        <section className="relative overflow-hidden px-6 py-24">
            {/* Background Image */}
            <div className="absolute inset-0 z-0">
                <img
                    src="/images/landing/data-pipeline.jpg"
                    alt="Data Pipeline Background"
                    width="1600"
                    height="900"
                    className="absolute inset-0 h-full w-full object-cover opacity-70"
                />
                <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background/50 to-background/60" />
            </div>

            <div className="relative z-10 mx-auto max-w-6xl">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Ключевые преимущества
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
                        Профессиональная аналитика без технических барьеров — focus на insights, а не на инструменты
                    </p>
                </div>

                <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                    {benefits.map((benefit) => (
                        <div
                            key={benefit.name}
                            className="group relative rounded-2xl border-2 border-[#21A038]/20 bg-card/80 backdrop-blur-sm p-6 transition-all duration-300 hover:scale-105 hover:border-[#21A038]/50 hover:shadow-xl hover:shadow-[#21A038]/10"
                        >
                            {/* Glow effect on hover */}
                            <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-primary/0 to-accent/0 opacity-0 transition-opacity duration-300 group-hover:opacity-10" />
                            <div className="mb-3 flex items-center gap-3">
                                <div
                                    className="relative flex h-14 w-14 items-center justify-center rounded-xl bg-[#21A038]/15 shadow-lg transition-all duration-300 group-hover:scale-110"
                                >
                                    <benefit.icon className="h-7 w-7 text-[#21A038] transition-transform duration-300 group-hover:scale-110" />
                                    {/* Pulse ring on hover */}
                                    <div className="absolute inset-0 rounded-xl bg-[#21A038]/20 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                                </div>
                                <span className="font-mono text-sm font-semibold text-foreground">{benefit.name}</span>
                            </div>
                            <p className="text-sm text-muted-foreground">{benefit.desc}</p>
                        </div>
                    ))}
                </div>

                <div className="mt-8 rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-6">
                    <h3 className="mb-4 text-center font-semibold text-foreground">Типичный workflow:</h3>
                    <p className="text-center text-muted-foreground">
                        <span className="font-mono text-blue-500">Data Source</span>
                        {' '}→<span className="text-xs mx-1">extract</span>→{' '}
                        <span className="font-mono text-purple-500">Raw Data</span>
                        {' '}→<span className="text-xs mx-1">transform</span>→{' '}
                        <span className="font-mono text-purple-500">Metrics</span>
                        {' '}→<span className="text-xs mx-1">visualize</span>→{' '}
                        <span className="font-mono text-green-500">Dashboard</span>
                    </p>
                    <p className="mt-4 text-center text-sm text-muted-foreground">
                        Автоматическое обновление при изменении источника данных
                    </p>
                </div>
            </div>
        </section>
    )
}

// Streaming & Real-time Section — NEW!
const StreamingSection = () => {
    return (
        <section id="streaming" className="relative overflow-hidden px-6 py-24">
            {/* Background Image */}
            <div className="absolute inset-0 z-0">
                <img
                    src="/images/landing/real-time-streaming.jpg"
                    alt="Real-Time Streaming Background"
                    width="1400"
                    height="1000"
                    className="absolute inset-0 h-full w-full object-cover opacity-70"
                />
                <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background/50 to-background/60" />
            </div>

            <div className="relative z-10 mx-auto max-w-6xl">
                <div className="text-center">
                    <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/10 px-4 py-2 text-sm font-medium text-accent-foreground">
                        <Radio className="h-4 w-4 text-accent animate-pulse" />
                        Real-time Streaming
                    </div>
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Живые данные в реальном времени
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
                        WebSocket, SSE, Kafka — GigaBoard поддерживает streaming источники с автоматической аккумуляцией и архивированием
                    </p>
                </div>

                <div className="mt-12 grid gap-8 lg:grid-cols-2">
                    <Card className="group relative overflow-hidden border-2 border-border/60 bg-gradient-to-br from-card via-accent/5 to-card backdrop-blur-sm transition-all duration-500 hover:scale-[1.03] hover:border-accent/70 hover:shadow-2xl hover:shadow-accent/20">
                        <CardHeader className="relative">
                            {/* Animated background gradient */}
                            <div className="absolute inset-0 bg-gradient-to-br from-accent/0 to-accent/10 opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
                            <div className="relative mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/20 shadow-xl transition-all duration-500 group-hover:scale-125 group-hover:shadow-2xl group-hover:rotate-6">
                                <Radio className="h-8 w-8 text-accent animate-pulse" />
                            </div>
                            <CardTitle className="text-2xl">Подключение потоков</CardTitle>
                            <CardDescription className="text-base leading-relaxed">
                                Подключайте любые источники данных реального времени. Данные автоматически сохраняются и обрабатываются.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <ul className="space-y-3">
                                {[
                                    'Аккумуляция в реальном времени',
                                    'Автоматическое архивирование',
                                    'Настраиваемые интервалы обновления',
                                    'Replay всей истории данных',
                                ].map((item) => (
                                    <li key={item} className="flex items-center gap-2 text-sm text-muted-foreground transition-colors group-hover:text-foreground">
                                        <CheckCircle2 className="h-4 w-4 shrink-0 text-success transition-transform group-hover:scale-110" />
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </CardContent>
                    </Card>

                    <Card className="group relative overflow-hidden border-2 border-border/60 bg-gradient-to-br from-card via-primary/5 to-card backdrop-blur-sm transition-all duration-500 hover:scale-[1.03] hover:border-primary/70 hover:shadow-2xl hover:shadow-primary/20">
                        <CardHeader className="relative">
                            {/* Animated background gradient */}
                            <div className="absolute inset-0 bg-gradient-to-br from-primary/0 to-primary/10 opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
                            <div className="relative mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/20 shadow-xl transition-all duration-500 group-hover:scale-125 group-hover:shadow-2xl group-hover:-rotate-6">
                                <RefreshCw className="h-8 w-8 text-primary transition-transform duration-500 group-hover:rotate-180" />
                            </div>
                            <CardTitle className="text-2xl">Умное обновление</CardTitle>
                            <CardDescription className="text-base leading-relaxed">
                                GigaBoard сам решает, когда и как обновлять ваши отчёты, чтобы не перегружать систему.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <ul className="space-y-3">
                                {[
                                    'Throttled: обновление не чаще N секунд',
                                    'Batched: накопление + batch обработка',
                                    'Manual: только по команде пользователя',
                                    'Intelligent: AI решает когда обновлять',
                                    'Selective: только изменённые части',
                                ].map((item) => (
                                    <li key={item} className="flex items-center gap-2 text-sm text-muted-foreground transition-colors group-hover:text-foreground">
                                        <Layers className="h-4 w-4 shrink-0 text-primary transition-transform group-hover:scale-110" />
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </CardContent>
                    </Card>
                </div>

                <div className="group relative mt-12 overflow-hidden rounded-2xl border border-accent/20 bg-gradient-to-r from-accent/10 via-primary/10 to-accent/10 p-6 shadow-xl transition-all hover:scale-[1.01] hover:border-accent/40 hover:shadow-2xl sm:p-8 backdrop-blur-sm">
                    <div className="absolute inset-0 bg-gradient-to-r from-accent/5 via-primary/5 to-accent/5 opacity-0 transition-opacity group-hover:opacity-100" />
                    <div className="relative flex items-start gap-4">
                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-accent/30 to-primary/30 shadow-lg">
                            <Radio className="h-6 w-6 text-accent animate-pulse" />
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-foreground mb-2">
                                🔴 Данные обновляются на глазах
                            </h3>
                            <p className="text-foreground/80 mb-4">
                                Пример: датчики IoT отправляют данные → GigaBoard получает их в реальном времени →
                                график обновляется мгновенно. Все видят изменения одновременно.
                            </p>
                            <div className="flex flex-wrap gap-2">
                                <span className="inline-flex items-center gap-1 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-accent-foreground">
                                    <Radio className="h-3 w-3" />
                                    Реальное время
                                </span>
                                <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary-foreground">
                                    <PlayCircle className="h-3 w-3" />
                                    Автообновление
                                </span>
                                <span className="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success/10 px-3 py-1 text-xs text-success-foreground">
                                    <Workflow className="h-3 w-3" />
                                    Для всех сразу
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    )
}

// AI Agents Section
// AI Agents Section — Multi-Agent System
const AgentsSection = () => {
    const agents = [
        {
            icon: Brain,
            name: 'Planner',
            role: 'Orchestrator',
            desc: 'Разбивает задачи на шаги, делегирует специализированным агентам, адаптирует план при ошибках',
            capabilities: ['Parsing user intent', 'Task decomposition', 'Adaptive replanning']
        },
        {
            icon: Search,
            name: 'Researcher',
            role: 'Data Fetcher',
            desc: 'Получает данные из API, баз данных, веб-страниц. Загружает полное содержимое найденных URL',
            capabilities: ['SQL queries', 'API calls', 'Web scraping (full content)']
        },
        {
            icon: PieChart,
            name: 'Analyst',
            role: 'Pattern Finder',
            desc: 'Анализирует данные из ContentNode, находит корреляции, тренды, аномалии и инсайты',
            capabilities: ['Statistical analysis', 'Pattern detection', 'Insight generation']
        },
        {
            icon: Terminal,
            name: 'Developer',
            role: 'Tool Builder',
            desc: 'Пишет custom tools на Python/SQL/JS для уникальных задач и web scraping',
            capabilities: ['Dynamic code generation', 'API integrations', 'Data parsers']
        },
        {
            icon: RefreshCw,
            name: 'Transformation',
            role: 'Data Pipeline',
            desc: 'Создаёт ContentNode трансформации с pandas: filter, groupby, merge, pivot',
            capabilities: ['Pandas operations', 'Data joins', 'Auto-replay on update']
        },
        {
            icon: Zap,
            name: 'Executor',
            role: 'Sandbox Runner',
            desc: 'Выполняет код в изолированной среде с resource limits и timeout контролем',
            capabilities: ['Isolated execution', 'Resource monitoring', 'Error handling']
        },
        {
            icon: FileOutput,
            name: 'Reporter',
            role: 'Visualization Gen',
            desc: 'Генерирует WidgetNode с полным HTML/CSS/JS кодом визуализации в iframe',
            capabilities: ['Chart.js charts', 'Custom HTML', 'Dark mode support']
        },
        {
            icon: FormInput,
            name: 'Form Generator',
            role: 'Input Builder',
            desc: 'Создаёт динамические формы с auto-detect источников и умными подсказками',
            capabilities: ['Schema inference', 'Validation rules', 'Conditional logic']
        },
        {
            icon: Globe,
            name: 'Data Discovery',
            role: 'Dataset Finder',
            desc: 'Находит публичные датасеты (Kaggle, OECD, World Bank) для пользователей без данных',
            capabilities: ['Kaggle search', 'OECD data', 'Public APIs']
        },
    ]

    return (
        <section id="agents" className="px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="text-center">
                    <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#21A038]/30 bg-[#21A038]/10 px-4 py-2 text-sm font-medium text-[#21A038]">
                        <Sparkles className="h-4 w-4" />
                        Multi-Agent System
                    </div>
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        9 специализированных AI-агентов
                    </h2>
                    <p className="mx-auto mt-4 max-w-3xl text-lg text-muted-foreground">
                        Команда агентов работает через <strong className="text-foreground">Message Bus</strong> (Redis),
                        обмениваясь задачами и результатами. Каждый агент — эксперт в своей области,
                        но вместе решают сложные аналитические задачи.
                    </p>
                </div>

                <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {agents.map((agent) => (
                        <div
                            key={agent.name}
                            className="group relative overflow-hidden rounded-xl border-2 border-[#21A038]/20 bg-card p-5 shadow-md transition-all duration-300 hover:scale-105 hover:border-[#21A038]/50 hover:shadow-lg hover:shadow-[#21A038]/10"
                        >
                            <div className="mb-3 flex items-start gap-3">
                                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-[#21A038]/15 transition-all duration-300 group-hover:scale-110">
                                    <agent.icon className="h-6 w-6 text-[#21A038]" />
                                </div>
                                <div className="flex-1">
                                    <h3 className="font-bold text-foreground">{agent.name}</h3>
                                    <p className="text-xs text-muted-foreground">{agent.role}</p>
                                </div>
                            </div>
                            <p className="mb-3 text-sm text-muted-foreground">{agent.desc}</p>
                            <div className="space-y-1">
                                {agent.capabilities.slice(0, 2).map((cap, idx) => (
                                    <div key={idx} className="flex items-center gap-2 text-xs text-muted-foreground">
                                        <div className="h-1 w-1 rounded-full bg-[#21A038]" />
                                        {cap}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Multi-Agent System Diagram Placeholder */}
                <div className="mt-12 rounded-2xl border-2 border-dashed border-[#21A038]/30 bg-muted/30 p-8">
                    <div className="flex flex-col items-center justify-center space-y-4 rounded-xl bg-muted/50 p-12">
                        <Network className="h-16 w-16 text-[#21A038]/60" />
                        <div className="text-center">
                            <p className="text-lg font-semibold text-foreground">🔄 Multi-Agent System Architecture</p>
                            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                                Диаграмма архитектуры мультиагентной системы:<br />
                                • Redis Message Bus в центре<br />
                                • 9 агентов вокруг (Planner, Researcher, Analyst, Developer, Transformation, Executor, Reporter, Form Generator, Data Discovery)<br />
                                • Стрелки показывают направление сообщений<br />
                                • Цветовая кодировка по типам каналов (broadcast, direct, ui_events)<br />
                                • В стиле Sber Green (#21A038)
                            </p>
                        </div>
                    </div>
                </div>

                {/* Critical Pattern: Search → Research → Analyze */}
                <div className="mt-12 rounded-2xl border-2 border-[#21A038]/30 bg-[#21A038]/5 p-8">
                    <div className="mb-6 flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#21A038]/20">
                            <Zap className="h-5 w-5 text-[#21A038]" />
                        </div>
                        <h3 className="text-xl font-bold text-foreground">
                            Критический паттерн: Search → Research → Analyze
                        </h3>
                    </div>
                    <div className="grid gap-4 lg:grid-cols-4">
                        {[
                            { num: '1', agent: 'Search Agent', action: 'Находит 5 релевантных URL', output: 'Snippets (150 символов)' },
                            { num: '2', agent: 'Researcher Agent', action: 'Загружает полный контент', output: '5000 символов на страницу' },
                            { num: '3', agent: 'Analyst Agent', action: 'Анализирует 20KB данных', output: 'Инсайты и паттерны' },
                            { num: '4', agent: 'Reporter Agent', action: 'Визуализирует результаты', output: 'WidgetNode графики' },
                        ].map((step) => (
                            <div key={step.num} className="rounded-lg border border-[#21A038]/20 bg-card p-4">
                                <div className="mb-2 flex items-center gap-2">
                                    <div className="flex h-6 w-6 items-center justify-center rounded bg-[#21A038]/20 text-sm font-bold text-[#21A038]">
                                        {step.num}
                                    </div>
                                    <h4 className="text-sm font-semibold text-foreground">{step.agent}</h4>
                                </div>
                                <p className="mb-2 text-xs text-muted-foreground">{step.action}</p>
                                <div className="rounded border border-border/50 bg-muted/50 px-2 py-1 text-xs font-mono text-muted-foreground">
                                    {step.output}
                                </div>
                            </div>
                        ))}
                    </div>
                    <p className="mt-4 text-center text-sm text-muted-foreground">
                        <strong className="text-foreground">40x больше данных</strong> для анализа благодаря промежуточному шагу Researcher Agent
                    </p>
                </div>

                {/* Agent Communication */}
                <div className="mt-12 grid gap-8 lg:grid-cols-2">
                    <div className="rounded-2xl border border-[#21A038]/30 bg-card p-6">
                        <h3 className="mb-4 flex items-center gap-3 text-lg font-semibold">
                            <div className="rounded-lg bg-[#21A038]/15 p-2">
                                <Network className="h-5 w-5 text-[#21A038]" />
                            </div>
                            Message Bus Communication
                        </h3>
                        <p className="mb-4 text-sm text-muted-foreground">
                            Агенты общаются через Redis Message Bus с 5 типами каналов:
                        </p>
                        <ul className="space-y-2">
                            {[
                                'Broadcast: для всех агентов',
                                'Direct: конкретному агенту',
                                'UI Events: обновления в реальном времени',
                                'Results: результаты выполнения',
                                'Errors: обработка ошибок'
                            ].map((item) => (
                                <li key={item} className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <div className="h-1.5 w-1.5 rounded-full bg-[#21A038]" />
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div className="rounded-2xl border border-[#21A038]/30 bg-card p-6">
                        <h3 className="mb-4 flex items-center gap-3 text-lg font-semibold">
                            <div className="rounded-lg bg-[#21A038]/15 p-2">
                                <Brain className="h-5 w-5 text-[#21A038]" />
                            </div>
                            Adaptive Planning
                        </h3>
                        <p className="mb-4 text-sm text-muted-foreground">
                            Planner Agent адаптирует план при изменении контекста:
                        </p>
                        <ul className="space-y-2">
                            {[
                                'Replan: если найдены новые источники данных',
                                'Retry: при временных ошибках с новыми параметрами',
                                'Abort: при критических ошибках',
                                'Ask User: когда контекст неоднозначен'
                            ].map((item) => (
                                <li key={item} className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <div className="h-1.5 w-1.5 rounded-full bg-[#21A038]" />
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>

                {/* Example Workflow */}
                <div className="group relative mt-8 overflow-hidden rounded-2xl border border-[#21A038]/30 bg-gradient-to-r from-[#21A038]/10 to-[#21A038]/5 p-8">
                    <div className="relative flex items-start gap-4">
                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#21A038]/20">
                            <Quote className="h-6 w-6 text-[#21A038]" />
                        </div>
                        <div>
                            <p className="text-lg font-medium italic text-foreground">
                                "Найди динамику безработицы в России и сравни с Европой"
                            </p>
                            <div className="mt-5 space-y-2 text-sm text-foreground/80">
                                <div className="flex items-center gap-2">
                                    <div className="h-2 w-2 rounded-full bg-[#21A038]" />
                                    <strong className="text-[#21A038]">Planner</strong> разбивает на шаги (Search → Research → Transform → Visualize)
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="h-2 w-2 rounded-full bg-[#21A038]" />
                                    <strong className="text-[#21A038]">Data Discovery</strong> находит датасеты Росстат, Eurostat
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="h-2 w-2 rounded-full bg-[#21A038]" />
                                    <strong className="text-[#21A038]">Researcher</strong> загружает полные данные через API
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="h-2 w-2 rounded-full bg-[#21A038]" />
                                    <strong className="text-[#21A038]">Transformation</strong> объединяет два датасета pandas merge
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="h-2 w-2 rounded-full bg-[#21A038]" />
                                    <strong className="text-[#21A038]">Analyst</strong> вычисляет тренды и корреляции
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="h-2 w-2 rounded-full bg-[#21A038]" />
                                    <strong className="text-[#21A038]">Reporter</strong> генерирует интерактивный line chart
                                </div>
                            </div>
                            <p className="mt-4 text-base font-semibold text-[#21A038]">
                                ✨ Полный data pipeline от промпта до дашборда за 30 секунд
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    )
}

// Widgets Section
// Widgets Section — AI-Generated Visualizations
const WidgetsSection = () => {
    const widgets = [
        {
            icon: BarChart3,
            name: 'Metric Cards',
            desc: 'KPI-карточки с трендами и цветовой индикацией',
            features: ['Положительный/отрицательный тренд', 'Умные иконки', 'Анимация чисел'],
            example: 'DAU: 12,345 ↑ +15%'
        },
        {
            icon: PieChart,
            name: 'Interactive Charts',
            desc: 'Линейные, столбчатые, круговые, area графики на Chart.js',
            features: ['Hover tooltips', 'Zoom и pan', 'Адаптивная легенда'],
            example: 'Динамика продаж за квартал'
        },
        {
            icon: Table,
            name: 'Data Tables',
            desc: 'Таблицы с сортировкой, фильтрацией и экспортом',
            features: ['Поиск по столбцам', 'Export CSV/Excel', 'Pagination'],
            example: 'Топ-100 клиентов по выручке'
        },
        {
            icon: LayoutGrid,
            name: 'Heatmaps',
            desc: 'Корреляционные матрицы и тепловые карты',
            features: ['Цветовые градиенты', 'Hover значения', 'Zoom области'],
            example: 'Корреляция метрик продукта'
        },
        {
            icon: Gauge,
            name: 'Gauges & Progress',
            desc: 'Индикаторы выполнения целей и состояния систем',
            features: ['Анимированные переходы', 'Цветовые зоны', 'Пороги'],
            example: 'Достижение квартального плана'
        },
        {
            icon: Code2,
            name: 'Custom Widgets',
            desc: 'Полностью кастомные визуализации с HTML/CSS/JS',
            features: ['Canvas API', 'D3.js / Three.js', 'WebGL графика'],
            example: '3D карты, network graphs, custom UI'
        },
    ]

    return (
        <section id="widgets" className="bg-muted/30 px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="text-center">
                    <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#21A038]/30 bg-[#21A038]/10 px-4 py-2 text-sm font-medium text-[#21A038]">
                        <Sparkles className="h-4 w-4" />
                        AI-Generated Visualizations
                    </div>
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Reporter Agent создаёт виджеты
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
                        AI генерирует <strong className="text-foreground">полный HTML/CSS/JS код</strong> для каждой визуализации — от простых графиков до сложных интерактивных компонентов. Без шаблонов, всегда с нуля.
                    </p>
                </div>

                <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                    {widgets.map((widget) => (
                        <div
                            key={widget.name}
                            className="group relative overflow-hidden rounded-2xl border-2 border-[#21A038]/20 bg-card p-6 shadow-md transition-all duration-300 hover:scale-105 hover:border-[#21A038]/50 hover:shadow-xl hover:shadow-[#21A038]/10"
                        >
                            <div className="mb-4 flex items-center gap-3">
                                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-[#21A038]/15 shadow-lg transition-all duration-300 group-hover:scale-110">
                                    <widget.icon className="h-7 w-7 text-[#21A038]" />
                                </div>
                                <h3 className="text-lg font-bold text-foreground">{widget.name}</h3>
                            </div>
                            <p className="mb-3 text-sm leading-relaxed text-muted-foreground">{widget.desc}</p>
                            <div className="mb-4 rounded-lg border border-border/50 bg-muted/50 px-3 py-2 text-xs font-mono text-muted-foreground">
                                {widget.example}
                            </div>
                            <ul className="space-y-2">
                                {widget.features.map((f) => (
                                    <li key={f} className="flex items-center gap-2 text-xs text-muted-foreground">
                                        <div className="h-1.5 w-1.5 rounded-full bg-[#21A038]" />
                                        {f}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                <div className="mt-12 rounded-2xl border border-[#21A038]/30 bg-[#21A038]/5 p-8">
                    <h3 className="mb-4 text-center text-xl font-bold text-foreground">
                        Как Reporter Agent генерирует виджеты
                    </h3>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        {[
                            { step: '1', title: 'Анализ данных', desc: 'AI анализирует ContentNode: структура, типы, паттерны' },
                            { step: '2', title: 'Генерация кода', desc: 'Пишет полный HTML/CSS/JS с Chart.js или Canvas API' },
                            { step: '3', title: 'Валидация', desc: 'Проверка безопасности, размера, производительности' },
                            { step: '4', title: 'Создание WidgetNode', desc: 'Связывается с ContentNode через VISUALIZATION edge' },
                        ].map((item) => (
                            <div key={item.step} className="text-center">
                                <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[#21A038]/20 text-lg font-bold text-[#21A038]">
                                    {item.step}
                                </div>
                                <h4 className="mb-1 text-sm font-semibold text-foreground">{item.title}</h4>
                                <p className="text-xs text-muted-foreground">{item.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="mt-8 text-center">
                    <p className="text-sm text-muted-foreground">
                        <strong className="text-foreground">Автообновление:</strong> при изменении родительского ContentNode все WidgetNode обновляются автоматически.<br />
                        <strong className="text-foreground">Responsive:</strong> все виджеты адаптированы для мобильных, планшетов и десктопов.<br />
                        <strong className="text-foreground">Dark Mode:</strong> поддержка тёмной темы через CSS переменные.
                    </p>
                </div>
            </div>
        </section>
    )
}

// Use Cases Section — Обновлённые примеры
const UseCasesSection = () => {
    // Маппинг ролей на названия файлов изображений
    const roleToImageName: Record<string, string> = {
        'Product Manager': 'product-manager',
        'Data Scientist': 'data-scientist',
        'DevOps Engineer': 'devops',
        'Студент / Исследователь': 'student',
    }

    const useCases = [
        {
            role: 'Product Manager',
            icon: Target,
            question: 'Покажи метрики продукта за неделю',
            result: 'AI создаёт полный дашборд за 30 секунд',
            steps: [
                'Подключается к базе данных',
                'Получает данные за неделю',
                'Группирует по дням',
                'Строит графики (активные пользователи, удержание, доход)',
                'Показывает всё на одной доске',
            ],
            badge: 'Без SQL',
        },
        {
            role: 'Data Scientist',
            icon: Brain,
            question: 'Проанализируй связь email-кампаний и покупок',
            result: 'Статистический анализ вместо часов в Python',
            steps: [
                'Анализирует данные о рассылках и покупках',
                'Вычисляет корреляцию (r=0.72)',
                'Определяет лучшее время эффекта',
                'Строит графики и таблицу',
                'Выводит инсайт: "Эффект заметен в день отправки"',
            ],
            badge: 'Автокод',
        },
        {
            role: 'DevOps Engineer',
            icon: AlertTriangle,
            question: 'Почему вчера ночью были ошибки?',
            result: 'Причина найдена за 5 минут',
            steps: [
                'Подключается к логам и истории развёртываний',
                'Сопоставляет время развёртывания и ошибок',
                'Находит: после v3.2.1 через 2 минуты начались ошибки',
                'Строит график временной линии',
                'Рекомендует: "Откатить на v3.2.0"',
            ],
            badge: 'Root Cause',
        },
        {
            role: 'Студент / Исследователь',
            icon: Globe,
            question: 'Проанализируй безработицу в России за 5 лет',
            result: 'Полный анализ без своих данных',
            steps: [
                'Ищет открытые данные (Росстат, ЦБ РФ, OECD)',
                'Подключает все источники',
                'Получает региональные данные',
                'Объединяет всё вместе',
                'Строит интерактивные графики и карту',
            ],
            badge: 'No Data? No Problem!',
        },
    ]

    return (
        <section id="use-cases" className="px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Примеры использования
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
                        AI делает всё автоматически — от получения данных до графиков
                    </p>
                </div>

                <div className="mt-12 grid gap-6 lg:grid-cols-2">
                    {useCases.map((useCase) => (
                        <Card key={useCase.role} className="group relative overflow-hidden border-2 border-border/60 bg-gradient-to-br from-card via-card/95 to-card/80 backdrop-blur-sm transition-all duration-500 hover:scale-[1.02] hover:border-primary/70 hover:shadow-2xl hover:shadow-primary/10">
                            {/* Animated shimmer effect */}
                            <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent transition-transform duration-1000 group-hover:translate-x-full" />
                            {/* Glow effect */}
                            <div className="absolute inset-0 bg-gradient-to-br from-primary/0 via-accent/0 to-primary/0 opacity-0 transition-opacity duration-500 group-hover:opacity-10" />
                            <CardHeader className="bg-primary/5 pb-4">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-accent/20 shadow-lg transition-all duration-300 group-hover:scale-125 group-hover:shadow-xl group-hover:rotate-12">
                                            <useCase.icon className="h-6 w-6 text-primary transition-transform duration-300 group-hover:scale-110" />
                                        </div>
                                        <CardTitle className="text-lg">{useCase.role}</CardTitle>
                                    </div>
                                    <span className="rounded-full border-2 border-accent/40 bg-gradient-to-r from-accent/20 to-accent/10 px-4 py-1.5 text-xs font-semibold text-accent-foreground shadow-lg backdrop-blur-sm transition-all duration-300 group-hover:scale-110 group-hover:border-accent/60 group-hover:shadow-xl">
                                        {useCase.badge}
                                    </span>
                                </div>
                                <CardDescription className="mt-2 italic text-foreground/80">
                                    "{useCase.question}"
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="pt-6">
                                {/* Use Case Illustration Placeholder */}
                                <div className="mb-6 overflow-hidden rounded-lg border-2 border-primary/30 bg-muted/50 relative">
                                    <img
                                        src={`/images/landing/use-case-${roleToImageName[useCase.role]}.jpg`}
                                        alt={`${useCase.role} working with data`}
                                        width="800"
                                        height="1000"
                                        className="w-full h-full object-cover"
                                    />
                                    <div className="absolute inset-0 bg-gradient-to-t from-background/90 to-transparent" />
                                    <div className="flex aspect-video items-center justify-center hidden">
                                        <div className="text-center">
                                            <Target className="mx-auto h-12 w-12 text-primary/60" />
                                            <p className="mt-2 text-xs font-medium text-muted-foreground">
                                                🎨 {useCase.role} Scenario
                                            </p>
                                            <p className="mt-1 max-w-xs text-xs text-muted-foreground/70">
                                                <strong>Prompt:</strong> Professional {useCase.role} character with data,<br />
                                                analytics elements, Sber Green theme, modern office
                                            </p>
                                        </div>
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    {useCase.steps.map((step, i) => (
                                        <div key={i} className="flex items-start gap-2 text-sm">
                                            <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                                                {i + 1}
                                            </div>
                                            <span className="text-muted-foreground">{step}</span>
                                        </div>
                                    ))}
                                </div>
                                <div className="mt-5 rounded-lg border border-success/30 bg-success/10 p-3">
                                    <p className="text-sm font-medium text-success-foreground">
                                        ✓ {useCase.result}
                                    </p>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </section>
    )
}

// Advanced Features Section (Drill-Down, Lineage, etc.)
const AdvancedFeaturesSection = () => {
    const features = [
        {
            icon: MousePointerClick,
            title: 'Interactive Drill-Down',
            description: 'Кликайте на элементы графиков для детализации. Многоуровневая навигация с breadcrumbs.',
            details: ['Click-to-Drill', 'Auto-Filter', 'Parent-Child Links', 'AI Suggestions'],
        },
        {
            icon: GitBranch,
            title: 'Data Lineage',
            description: 'Визуализация полного пути данных от источника до виджета. Impact Analysis.',
            details: ['DAG-граф', 'Root Cause Analysis', 'Audit Trail', 'Change Alerts'],
        },
        {
            icon: MessageSquare,
            title: 'Collaborative Annotations',
            description: 'Комментарии и аннотации на виджетах. @Mentions, треды обсуждений, AI участие.',
            details: ['Widget Comments', '@Mentions', 'Thread Discussions', 'Visual Markers'],
        },
        {
            icon: Share2,
            title: 'Export & Embedding',
            description: 'Экспорт в PDF, PowerPoint, PNG. Встраивание виджетов на внешние сайты.',
            details: ['Multiple Formats', 'Public Share Links', 'Embed Snippets', 'Access Control'],
        },
    ]

    return (
        <section className="bg-muted/30 px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Продвинутые возможности
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
                        Enterprise-функции для глубокого анализа и командной работы
                    </p>
                </div>

                <div className="mt-12 grid gap-6 sm:grid-cols-2">
                    {features.map((feature) => (
                        <div key={feature.title} className="rounded-2xl border border-border bg-card p-6">
                            <div className="mb-4 flex items-center gap-3">
                                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                                    <feature.icon className="h-6 w-6 text-primary" />
                                </div>
                                <h3 className="text-lg font-semibold text-foreground">{feature.title}</h3>
                            </div>
                            <p className="mb-4 text-muted-foreground">{feature.description}</p>
                            <div className="flex flex-wrap gap-2">
                                {feature.details.map((d) => (
                                    <span key={d} className="rounded-full border border-border bg-background px-3 py-1 text-xs text-muted-foreground">
                                        {d}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    )
}

// Upcoming Features Section
const UpcomingFeaturesSection = () => {
    const features = [
        { icon: Mic, title: 'Голосовой ввод', desc: 'Voice-to-Text для hands-free работы', status: 'Планируется' },
        { icon: Calendar, title: 'Автоматические отчёты', desc: 'Отчёты по расписанию в Slack, Email, Teams', status: 'Планируется' },
        { icon: Languages, title: 'Мультиязычность', desc: 'Русский, English, 中文, Español', status: 'Планируется' },
        { icon: Download, title: 'Маркетплейс шаблонов', desc: 'Библиотека готовых виджетов и досок', status: 'Планируется' },
    ]

    return (
        <section className="px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Скоро в GigaBoard
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
                        Мы постоянно развиваем платформу
                    </p>
                </div>

                <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {features.map((feature) => (
                        <div key={feature.title} className="rounded-xl border border-dashed border-border p-5 text-center">
                            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-muted">
                                <feature.icon className="h-6 w-6 text-muted-foreground" />
                            </div>
                            <h3 className="font-semibold text-foreground">{feature.title}</h3>
                            <p className="mt-1 text-sm text-muted-foreground">{feature.desc}</p>
                            <span className="mt-3 inline-block rounded-full bg-warning/10 px-2 py-1 text-xs text-warning">
                                {feature.status}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    )
}

// Security Section
const SecuritySection = () => {
    const features = [
        { icon: Shield, title: 'Изолированное выполнение', desc: 'Sandbox с Docker/процессной изоляцией' },
        { icon: Clock, title: 'Лимиты ресурсов', desc: 'Timeout, memory limit, disk limit' },
        { icon: Key, title: 'JWT-авторизация', desc: 'Безопасный доступ к данным' },
        { icon: FileText, title: 'Аудит действий', desc: 'Полное логирование операций' },
        { icon: Eye, title: 'Code Validation', desc: 'Проверка кода перед выполнением' },
        { icon: Database, title: 'Encrypted Credentials', desc: 'Шифрование учётных данных' },
    ]

    return (
        <section id="security" className="bg-muted/30 px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="grid items-center gap-12 lg:grid-cols-2">
                    <div>
                        <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                            Безопасность на первом месте
                        </h2>
                        <p className="mt-4 text-muted-foreground">
                            Ваши данные и код защищены современными технологиями безопасности
                        </p>
                        <div className="mt-8 grid gap-4 sm:grid-cols-2">
                            {features.map((feature) => (
                                <div key={feature.title} className="flex items-start gap-3">
                                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-success/10">
                                        <feature.icon className="h-4 w-4 text-success" />
                                    </div>
                                    <div>
                                        <h3 className="font-medium text-foreground">{feature.title}</h3>
                                        <p className="text-sm text-muted-foreground">{feature.desc}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="rounded-2xl border border-border bg-card p-6">
                        <div className="flex items-center gap-3 border-b border-border pb-4">
                            <div className="h-3 w-3 rounded-full bg-red-500" />
                            <div className="h-3 w-3 rounded-full bg-yellow-500" />
                            <div className="h-3 w-3 rounded-full bg-green-500" />
                            <span className="ml-2 text-sm text-muted-foreground">tool_sandbox.py</span>
                        </div>
                        <pre className="mt-4 overflow-x-auto text-sm text-muted-foreground">
                            <code>{`# Безопасное выполнение инструментов
class ToolSandbox:
    def execute(self, code: str):
        # Валидация кода
        self.validate_code(code)
        
        # Запуск в изоляции
        result = sandbox.run(
            code=code,
            timeout=30,
            memory_limit="512MB",
            network=False,  # Без сети
            allowed_libs=WHITELIST
        )
        
        # Логирование
        audit.log(
            action="tool_execution",
            code_hash=hash(code),
            status=result.status
        )
        
        return result`}</code>
                        </pre>
                    </div>
                </div>
            </div>
        </section>
    )
}

// Tech Stack Section
const TechStackSection = () => {
    const stack = [
        { category: 'Frontend', items: ['React + TypeScript', 'Vite', 'React Flow', 'Zustand', 'TanStack Query', 'Tailwind CSS', 'ShadCN UI'] },
        { category: 'Backend', items: ['FastAPI', 'Python 3.13', 'SQLAlchemy', 'Pydantic v2', 'Alembic', 'Socket.IO'] },
        { category: 'AI', items: ['GigaChat', 'LangChain', 'langchain-gigachat', 'Adaptive Planning'] },
        { category: 'Real-time', items: ['Socket.IO', 'Redis Pub/Sub', 'WebSocket', 'SSE', 'Message Bus'] },
        { category: 'Database', items: ['PostgreSQL', 'Redis Cache', 'Stream Archives'] },
    ]

    return (
        <section className="px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Технологический стек
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
                        Современные технологии для надёжной и масштабируемой системы
                    </p>
                </div>

                <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
                    {stack.map((s) => (
                        <div key={s.category} className="rounded-xl border border-border bg-card p-4 transition-all hover:scale-105 hover:border-primary/30 hover:shadow-lg">
                            <h3 className="mb-3 font-semibold text-foreground">{s.category}</h3>
                            <ul className="space-y-1">
                                {s.items.map((item) => (
                                    <li key={item} className="text-sm text-muted-foreground">{item}</li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                <div className="mt-8 grid gap-4 sm:grid-cols-3">
                    <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 text-center">
                        <p className="text-sm font-medium text-foreground">Понятная структура</p>
                        <p className="mt-1 text-xs text-muted-foreground">От источника к результату</p>
                    </div>
                    <div className="rounded-lg border border-accent/20 bg-accent/5 p-4 text-center">
                        <p className="text-sm font-medium text-foreground">9 AI-помощников</p>
                        <p className="mt-1 text-xs text-muted-foreground">Работают как команда</p>
                    </div>
                    <div className="rounded-lg border border-success/20 bg-success/5 p-4 text-center">
                        <p className="text-sm font-medium text-foreground">Быстрый ответ</p>
                        <p className="mt-1 text-xs text-muted-foreground">Результат за секунды</p>
                    </div>
                </div>
            </div>
        </section>
    )
}

// Testimonials Section
const TestimonialsSection = () => {
    const testimonials = [
        {
            quote: 'Раньше я тратил 2 часа на создание отчёта в Tableau. С GigaBoard — 15 минут.',
            author: 'Аналитик данных',
        },
        {
            quote: 'AI-ассистент понимает контекст моей доски и предлагает именно то, что нужно.',
            author: 'Product Manager',
        },
        {
            quote: 'Командная работа в реальном времени изменила то, как мы обсуждаем данные.',
            author: 'Руководитель отдела аналитики',
        },
    ]

    return (
        <section className="bg-gradient-to-b from-muted/30 to-background px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Что говорят пользователи
                    </h2>
                </div>

                <div className="mt-12 grid gap-8 lg:grid-cols-3">
                    {testimonials.map((testimonial, i) => (
                        <Card key={i} className="relative overflow-hidden">
                            <CardContent className="pt-6">
                                <div className="mb-4 flex gap-1">
                                    {[...Array(5)].map((_, j) => (
                                        <Star key={j} className="h-4 w-4 fill-warning text-warning" />
                                    ))}
                                </div>
                                <p className="italic text-muted-foreground">
                                    "{testimonial.quote}"
                                </p>
                                <p className="mt-4 font-medium text-foreground">
                                    — {testimonial.author}
                                </p>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </section>
    )
}

// Target Audience Section
const TargetAudienceSection = () => {
    const audiences = [
        { role: 'Product Manager', benefit: 'Мгновенный анализ метрик без SQL' },
        { role: 'Data Analyst', benefit: 'Визуализации за секунды, не за часы' },
        { role: 'Data Scientist', benefit: 'Быстрая проверка гипотез с AI' },
        { role: 'DevOps/SRE', benefit: 'Анализ инцидентов в реальном времени' },
        { role: 'Руководитель', benefit: 'Дашборды для принятия решений' },
        { role: 'Студент', benefit: 'Анализ публичных данных для исследований' },
        { role: 'Журналист', benefit: 'Data-journalism без программирования' },
        { role: 'Маркетолог', benefit: 'ROI кампаний и attribution анализ' },
    ]

    return (
        <section id="audience" className="px-6 py-24">
            <div className="mx-auto max-w-6xl">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                        Для кого GigaBoard?
                    </h2>
                </div>

                <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {audiences.map((item) => (
                        <div
                            key={item.role}
                            className="flex items-center gap-3 rounded-xl border border-border/50 bg-card p-4 transition-all hover:border-primary/30"
                        >
                            <CheckCircle2 className="h-5 w-5 shrink-0 text-primary" />
                            <div>
                                <h3 className="font-semibold text-foreground">{item.role}</h3>
                                <p className="text-sm text-muted-foreground">{item.benefit}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    )
}

// CTA Section
const CTASection = () => (
    <section className="px-6 py-24">
        <div className="mx-auto max-w-4xl">
            <div className="relative overflow-hidden rounded-3xl border-2 border-[#21A038] bg-card/80 p-8 text-center backdrop-blur-sm sm:p-16">
                <div className="relative">
                    <h2 className="text-5xl font-bold text-foreground sm:text-6xl">
                        Готовы к революции в аналитике?
                    </h2>
                    <p className="mx-auto mt-6 max-w-xl text-xl leading-relaxed text-muted-foreground">
                        Попрощайтесь с бесконечными SQL запросами и часами ручной работы.
                        <br />
                        <span className="font-semibold text-[#21A038]">Просто опишите задачу — AI построит весь pipeline.</span>
                    </p>
                    <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
                        <Link to="/register">
                            <Button size="lg" className="gap-2 bg-[#21A038] px-10 py-7 text-lg font-semibold text-white transition-all hover:bg-[#1a8030] hover:scale-105">
                                <span>Начать бесплатно</span>
                                <ArrowRight className="h-5 w-5" />
                            </Button>
                        </Link>
                    </div>

                    {/* Trust indicators */}
                    <div className="mt-12 flex flex-wrap items-center justify-center gap-8 text-muted-foreground">
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="h-5 w-5 text-[#21A038]" />
                            <span className="text-sm">Бесплатный старт</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="h-5 w-5 text-[#21A038]" />
                            <span className="text-sm">Без кредитной карты</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="h-5 w-5 text-[#21A038]" />
                            <span className="text-sm">Готово за 2 минуты</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
)

// Footer
const Footer = () => (
    <footer className="border-t border-border bg-card/50 px-6 py-12">
        <div className="mx-auto max-w-6xl">
            <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
                <div className="flex items-center gap-2">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                        <Layout className="h-6 w-6" />
                    </div>
                    <span className="text-xl font-bold text-foreground">GigaBoard</span>
                </div>
                <p className="text-sm text-muted-foreground">
                    © {new Date().getFullYear()} GigaBoard Inc. Все права защищены.
                </p>
            </div>
            <div className="mt-8 text-center">
                <p className="text-sm text-muted-foreground">
                    Ваши данные. Ваши инсайты. Ваш AI-помощник.
                </p>
            </div>
        </div>
    </footer>
)

// Header/Navbar
const Header = () => (
    <header className="sticky top-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl shadow-sm">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
            <Link to="/" className="flex items-center gap-2 transition-transform hover:scale-105">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent shadow-lg text-primary-foreground transition-shadow hover:shadow-xl">
                    <Layout className="h-6 w-6" />
                </div>
                <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-xl font-bold text-transparent">
                    GigaBoard
                </span>
            </Link>

            <nav className="hidden items-center gap-6 lg:flex">
                <a href="#features" className="text-sm font-medium text-muted-foreground transition-all hover:text-primary hover:scale-110">
                    Архитектура
                </a>
                <a href="#streaming" className="text-sm font-medium text-muted-foreground transition-all hover:text-primary hover:scale-110">
                    Streaming
                </a>
                <a href="#agents" className="text-sm font-medium text-muted-foreground transition-all hover:text-primary hover:scale-110">
                    AI-агенты
                </a>
                <a href="#use-cases" className="text-sm font-medium text-muted-foreground transition-all hover:text-primary hover:scale-110">
                    Примеры
                </a>
                <a href="#security" className="text-sm font-medium text-muted-foreground transition-all hover:text-primary hover:scale-110">
                    Безопасность
                </a>
            </nav>

            <div className="flex items-center gap-4">
                <Link to="/login">
                    <Button variant="ghost" size="sm" className="transition-all hover:scale-105">
                        Войти
                    </Button>
                </Link>
                <Link to="/register">
                    <Button size="sm" className="shadow-lg shadow-primary/25 transition-all hover:scale-105 hover:shadow-xl hover:shadow-primary/30">
                        Начать
                    </Button>
                </Link>
            </div>
        </div>
    </header>
)

// Main Landing Page Component
export const LandingPage = () => {
    // Force dark theme for landing page only
    useEffect(() => {
        const root = document.documentElement
        const previousTheme = root.classList.contains('dark') ? 'dark' : 'light'

        // Set dark theme
        root.classList.add('dark')
        root.classList.remove('light')

        // Restore previous theme on unmount
        return () => {
            if (previousTheme === 'light') {
                root.classList.remove('dark')
                root.classList.add('light')
            }
        }
    }, [])

    return (
        <div className="min-h-screen bg-background">
            <Header />
            <main>
                <HeroSection />
                <CoreFeaturesSection />
                <BenefitsSection />
                <StreamingSection />
                <AgentsSection />
                <WidgetsSection />
                <UseCasesSection />
                <AdvancedFeaturesSection />
                <UpcomingFeaturesSection />
                <SecuritySection />
                <TechStackSection />
                <TestimonialsSection />
                <TargetAudienceSection />
                <CTASection />
            </main>
            <Footer />
        </div>
    )
}
