import { Link } from 'react-router-dom'
import { useState } from 'react'
import {
    ArrowRight,
    CheckCircle2,
    Clock,
    Image as ImageIcon,
    LayoutDashboard,
    MessageCircle,
    Sparkles,
    Users,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Logo } from '@/components/Logo'

const BRAND = '#21A038'

/** Показывает изображение; при отсутствии файла — плейсхолдер с подсказкой. Промпты: docs/LANDING_IMAGE_PROMPTS.md */
const LandingIllustration = ({
    src,
    alt,
    caption,
    aspectClassName = 'aspect-[16/10]',
}: {
    src: string
    alt: string
    caption: string
    aspectClassName?: string
}) => {
    const [failed, setFailed] = useState(false)

    if (failed) {
        return (
            <div
                className={`flex w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-muted-foreground/30 bg-muted/25 px-3 py-8 text-center ${aspectClassName}`}
            >
                <ImageIcon className="h-9 w-9 text-muted-foreground/45" aria-hidden />
                <p className="text-xs font-medium leading-snug text-muted-foreground">{caption}</p>
                <p className="break-all font-mono text-[10px] leading-tight text-muted-foreground/55">{src}</p>
            </div>
        )
    }

    return (
        <div className={`relative w-full overflow-hidden rounded-xl bg-muted/20 ring-1 ring-border/60 ${aspectClassName}`}>
            <img src={src} alt={alt} className="h-full w-full object-cover" onError={() => setFailed(true)} loading="lazy" />
        </div>
    )
}

const SectionHeader = ({
    eyebrow,
    title,
    description,
}: {
    eyebrow?: string
    title: string
    description?: string
}) => (
    <div className="mx-auto max-w-2xl text-center">
        {eyebrow ? (
            <p
                className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em]"
                style={{ color: BRAND }}
            >
                {eyebrow}
            </p>
        ) : null}
        <h2 className="text-balance text-3xl font-bold tracking-tight text-foreground md:text-4xl">{title}</h2>
        {description ? <p className="mt-4 text-lg leading-relaxed text-muted-foreground">{description}</p> : null}
    </div>
)

const HeroSection = () => (
    <section className="relative overflow-hidden bg-black px-6 pb-24 pt-24 sm:pb-32 sm:pt-28 lg:pb-36 lg:pt-32">
        <div className="pointer-events-none absolute inset-0 z-0">
            <img
                src="/images/landing/hero-background.jpg"
                alt=""
                width={2400}
                height={1200}
                className="absolute inset-0 h-full w-full object-cover opacity-[0.45]"
            />
            <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/45 to-black" />
            <div className="absolute inset-0 bg-gradient-to-r from-black/55 via-transparent to-black/55" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(33,160,56,0.12),transparent)]" />
        </div>

        <div className="relative z-10 mx-auto max-w-4xl text-center">
            <div className="mb-8 flex justify-center">
                <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.07] px-5 py-2.5 text-sm font-medium text-white/95 shadow-lg shadow-black/20 backdrop-blur-md">
                    <Sparkles className="h-4 w-4" style={{ color: BRAND }} />
                    Аналитика с ИИ — без лишней суеты
                </div>
            </div>

            <h1 className="mx-auto mb-6 max-w-4xl text-balance text-4xl font-bold leading-[1.12] tracking-tight text-white sm:text-5xl lg:text-[3.25rem]">
                От источника к инсайту{' '}
                <span className="block sm:inline" style={{ color: BRAND }}>
                    — быстрее с ИИ
                </span>
            </h1>
            <p className="mx-auto max-w-2xl text-balance text-lg leading-relaxed text-white/80 sm:text-xl">
                <strong className="font-semibold text-white">GigaBoard</strong> — аналитика на доске-пайплайне с ИИ: наглядный путь от
                данных к графикам и дашбордам, общие фильтры и диалог про результаты исследований.
            </p>

            <div className="mt-11 flex flex-col items-center justify-center gap-4 sm:flex-row sm:gap-5">
                <Link to="/register">
                    <Button
                        size="lg"
                        className="h-14 min-w-[220px] gap-2 rounded-xl bg-[#21A038] px-8 text-base font-semibold text-white shadow-lg shadow-[#21A038]/25 transition-all hover:bg-[#1a8030] hover:shadow-xl hover:shadow-[#21A038]/30"
                    >
                        Попробовать бесплатно
                        <ArrowRight className="h-5 w-5" />
                    </Button>
                </Link>
                <Link to="/login">
                    <Button
                        variant="outline"
                        size="lg"
                        className="h-14 min-w-[200px] rounded-xl border-white/25 bg-white/[0.06] px-8 text-base font-semibold text-white backdrop-blur-sm transition-colors hover:bg-white/12"
                    >
                        Уже есть аккаунт
                    </Button>
                </Link>
            </div>

            <div className="mx-auto mt-16 grid max-w-3xl grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
                {[
                    { icon: MessageCircle, text: 'Пишете задачу обычным языком' },
                    { icon: LayoutDashboard, text: 'Доска, дашборд и фильтры в одном контексте' },
                    { icon: Users, text: 'Удобно вместе с командой' },
                ].map(({ icon: Icon, text }) => (
                    <div
                        key={text}
                        className="flex min-h-[3.5rem] items-center justify-center gap-2.5 rounded-2xl border border-white/12 bg-white/[0.06] px-4 py-3.5 text-left text-sm font-medium leading-snug text-white/95 shadow-inner shadow-black/20 backdrop-blur-md sm:text-center"
                    >
                        <Icon className="h-4 w-4 shrink-0" style={{ color: BRAND }} />
                        <span>{text}</span>
                    </div>
                ))}
            </div>
        </div>
    </section>
)

const ValueSection = () => {
    const items = [
        {
            title: 'Всё на одном экране',
            text: 'Источники, расчёты и визуализации связаны наглядно на доске; нужный срез можно вынести на дашборд и вести общий показ. Понятно, откуда взялись цифры и что с ними сделали.',
            imageSrc: '/images/landing/value-canvas.jpg',
            imageCaption: 'Иллюстрация: единое полотно пайплайна',
        },
        {
            title: 'ИИ рядом с вами',
            text: 'Опишите задачу в диалоге — ассистент опирается на контекст доски и дашборда: таблицы, узлы и собранные виджеты. Без необходимости быть программистом.',
            imageSrc: '/images/landing/value-ai-dialog.jpg',
            imageCaption: 'Иллюстрация: диалог с ИИ у данных',
        },
        {
            title: 'Дашборды и общий контекст',
            text: 'Соберите макет для руководства или встречи: на дашборде задайте общие фильтры — один срез обновляет все виджеты (сквозная фильтрация по измерениям). Одна картина по метрикам на экране.',
            imageSrc: '/images/landing/value-dashboard.jpg',
            imageCaption: 'Иллюстрация: дашборд для показа',
        },
    ]

    return (
        <section id="value" className="relative border-t border-border/40 px-6 py-24 md:py-28">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_100%_80%_at_50%_0%,hsl(var(--primary)/0.06),transparent)]" />
            <div className="relative mx-auto max-w-6xl">
                <SectionHeader
                    eyebrow="Ценность"
                    title="Прозрачная цепочка от вопроса к выводу"
                    description="ИИ убирает лишнюю возню с формулировками и черновиками, а воспроизводимость и контроль остаются с вами."
                />
                <div className="mt-14 grid gap-6 md:grid-cols-3 md:gap-8">
                    {items.map((item) => (
                        <Card
                            key={item.title}
                            className="group flex flex-col overflow-hidden border-border/60 bg-card/60 shadow-sm backdrop-blur-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-[#21A038]/25 hover:shadow-lg hover:shadow-black/5"
                        >
                            <div className="border-b border-border/40 p-3">
                                <LandingIllustration
                                    src={item.imageSrc}
                                    alt=""
                                    caption={item.imageCaption}
                                />
                            </div>
                            <CardHeader className="space-y-4 pb-6 pt-6">
                                <CardTitle className="text-xl font-semibold tracking-tight">{item.title}</CardTitle>
                                <CardDescription className="text-base leading-relaxed text-muted-foreground">{item.text}</CardDescription>
                            </CardHeader>
                        </Card>
                    ))}
                </div>
            </div>
        </section>
    )
}

const HowItWorksSection = () => {
    const steps = [
        {
            n: '1',
            title: 'Подключите данные',
            text: 'Файлы, базы, API или открытые источники — что подходит вашей задаче.',
        },
        {
            n: '2',
            title: 'Сформулируйте вопрос',
            text: 'Напишите, что хотите сравнить, отфильтровать или объяснить. ИИ поможет уточнить формулировку.',
        },
        {
            n: '3',
            title: 'Смотрите результат',
            text: 'Таблицы и графики на доске, при необходимости — собранный показ на дашборде с общими фильтрами. Краткие выводы рядом; при обновлении входных данных цепочка может пересчитаться сама.',
        },
    ]

    return (
        <section id="how" className="relative overflow-hidden border-t border-border/40 px-6 py-24 md:py-28">
            <div className="absolute inset-0 z-0">
                <img
                    src="/images/landing/data-pipeline.jpg"
                    alt=""
                    width={1600}
                    height={900}
                    className="absolute inset-0 h-full w-full object-cover opacity-[0.35]"
                />
                <div className="absolute inset-0 bg-gradient-to-b from-background via-background/[0.97] to-background" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_20%,hsl(var(--card)_/_0.35),transparent)]" />
            </div>
            <div className="relative z-10 mx-auto max-w-3xl">
                <SectionHeader
                    eyebrow="Процесс"
                    title="Как это выглядит в работе"
                    description="Простым языком: три шага от источников до графиков и выводов."
                />
                <div className="mt-10">
                    <LandingIllustration
                        src="/images/landing/how-process-overview.jpg"
                        alt=""
                        caption="Иллюстрация: путь от источника к инсайту"
                        aspectClassName="aspect-[21/9]"
                    />
                </div>
                <div className="relative mt-10">
                    <div
                        className="pointer-events-none absolute left-[1.375rem] top-10 hidden h-[calc(100%-3rem)] w-px bg-gradient-to-b from-[#21A038]/40 via-border/80 to-transparent md:block"
                        aria-hidden
                    />
                    <ol className="space-y-5">
                        {steps.map((step) => (
                            <li
                                key={step.n}
                                className="flex gap-5 rounded-2xl border border-border/70 bg-card/85 p-6 shadow-md backdrop-blur-md md:gap-6 md:p-8"
                            >
                                <span className="relative z-10 flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#21A038] text-base font-bold text-white shadow-lg shadow-[#21A038]/25 ring-4 ring-background">
                                    {step.n}
                                </span>
                                <div className="min-w-0 pt-0.5">
                                    <h3 className="text-lg font-semibold tracking-tight text-foreground">{step.title}</h3>
                                    <p className="mt-2 leading-relaxed text-muted-foreground">{step.text}</p>
                                </div>
                            </li>
                        ))}
                    </ol>
                </div>
            </div>
        </section>
    )
}

const StoriesSection = () => {
    const stories = [
        {
            role: 'Менеджер продукта',
            quote: '«Покажи активность и удержание за неделю»',
            outcome: 'Через минуты — картина по метрикам на одной доске, без очереди к аналитику.',
            imageSrc: '/images/landing/story-product.jpg',
            imageCaption: 'Иллюстрация: метрики продукта',
        },
        {
            role: 'Аналитик или исследователь',
            quote: '«Сравни два сегмента и проверь гипотезу»',
            outcome: 'Меньше ручного кода на черновик: можно быстро проверить идею и показать коллегам.',
            imageSrc: '/images/landing/story-analyst.jpg',
            imageCaption: 'Иллюстрация: сравнение и гипотезы',
        },
        {
            role: 'Команда на встрече',
            quote: '«Обновили цифры — все видят то же самое»',
            outcome: 'Один дашборд с общими фильтрами: смотрите на согласованную картину и обсуждайте план без расхождений в срезе.',
            imageSrc: '/images/landing/story-team.jpg',
            imageCaption: 'Иллюстрация: общая картина в команде',
        },
    ]

    return (
        <section id="examples" className="border-t border-border/40 bg-muted/20 px-6 py-24 md:py-28">
            <div className="mx-auto max-w-6xl">
                <SectionHeader
                    eyebrow="Сценарии"
                    title="Разные задачи — одна доска"
                    description="Продукт, аналитика, командный созвон: связанные цифры и выводы остаются на одном полотне."
                />
                <div className="mt-14 grid gap-6 md:grid-cols-3 md:gap-8">
                    {stories.map((s) => (
                        <Card
                            key={s.role}
                            className="flex flex-col overflow-hidden border-border/60 bg-card/80 shadow-sm transition-all duration-300 hover:border-[#21A038]/20 hover:shadow-md"
                        >
                            <div className="h-1 bg-gradient-to-r from-[#21A038] to-[#21A038]/40" />
                            <div className="border-b border-border/50 p-2">
                                <LandingIllustration
                                    src={s.imageSrc}
                                    alt=""
                                    caption={s.imageCaption}
                                    aspectClassName="aspect-[4/3]"
                                />
                            </div>
                            <CardHeader className="space-y-4 pb-4 pt-5">
                                <CardTitle className="text-lg font-semibold">{s.role}</CardTitle>
                                <CardDescription className="text-base italic leading-relaxed text-foreground/90">{s.quote}</CardDescription>
                            </CardHeader>
                            <CardContent className="mt-auto border-t border-border/40 bg-muted/20 pb-7 pt-5">
                                <p className="text-sm leading-relaxed text-muted-foreground">{s.outcome}</p>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </section>
    )
}

const CTASection = () => (
    <section className="border-t border-border/40 px-6 py-24 md:py-28">
        <div className="mx-auto max-w-3xl text-center">
            <div className="relative overflow-hidden rounded-3xl border border-[#21A038]/20 bg-gradient-to-b from-card to-card/80 px-8 py-12 shadow-2xl shadow-black/20 md:px-14 md:py-16">
                <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[#21A038]/10 blur-3xl" />
                <div className="pointer-events-none absolute -bottom-24 -left-16 h-56 w-56 rounded-full bg-primary/5 blur-3xl" />
                <div className="relative">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#21A038]">Старт</p>
                    <h2 className="mt-3 text-balance text-3xl font-bold tracking-tight text-foreground md:text-4xl">
                        Попробуйте на своём вопросе
                    </h2>
                    <p className="mx-auto mt-4 max-w-lg text-lg text-muted-foreground">
                        Зарегистрируйтесь и загрузите первый источник — или откройте демо-данные, если они есть в вашей среде.
                    </p>
                    <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row sm:gap-5">
                        <Link to="/register">
                            <Button
                                size="lg"
                                className="h-14 min-w-[200px] gap-2 rounded-xl bg-[#21A038] px-8 text-base font-semibold shadow-lg shadow-[#21A038]/20 hover:bg-[#1a8030]"
                            >
                                Создать аккаунт
                                <ArrowRight className="h-5 w-5" />
                            </Button>
                        </Link>
                        <Link to="/login">
                            <Button variant="outline" size="lg" className="h-14 min-w-[140px] rounded-xl px-8 text-base font-semibold">
                                Войти
                            </Button>
                        </Link>
                    </div>
                    <div className="mt-10 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm text-muted-foreground">
                        <span className="inline-flex items-center gap-2">
                            <CheckCircle2 className="h-4 w-4 shrink-0 text-[#21A038]" />
                            Без карты на старте
                        </span>
                        <span className="inline-flex items-center gap-2">
                            <Clock className="h-4 w-4 shrink-0 text-[#21A038]" />
                            Минуты до первого графика
                        </span>
                    </div>
                </div>
            </div>
        </div>
    </section>
)

const Footer = () => (
    <footer className="border-t border-border/60 bg-card/40 px-6 py-12">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 sm:flex-row sm:items-start">
            <div className="flex flex-col items-center gap-2 sm:items-start">
                <Logo variant="dark" size={36} className="shrink-0" />
                <p className="max-w-xs text-center text-sm text-muted-foreground sm:text-left">
                    Данные, вопросы и ответы — на одной доске.
                </p>
            </div>
            <p className="text-center text-sm text-muted-foreground/90 sm:text-right">
                © {new Date().getFullYear()} GigaBoard
            </p>
        </div>
    </footer>
)

const Header = () => (
    <header className="sticky top-0 z-50 border-b border-gray-200/90 bg-white/95 shadow-sm backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-6">
            <a
                href="/"
                className="flex shrink-0 items-center rounded-md outline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#21A038]"
            >
                <Logo
                    variant="light"
                    link={false}
                    size={32}
                    className="shrink-0 [&_span.text-xl]:!text-gray-900"
                />
            </a>

            <nav className="hidden items-center gap-1 md:flex">
                {[
                    { href: '#value', label: 'Зачем' },
                    { href: '#how', label: 'Как работает' },
                    { href: '#examples', label: 'Кому' },
                ].map((item) => (
                    <a
                        key={item.href}
                        href={item.href}
                        className="rounded-lg px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900"
                    >
                        {item.label}
                    </a>
                ))}
            </nav>

            <div className="flex items-center gap-2">
                <Link to="/login">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                    >
                        Войти
                    </Button>
                </Link>
                <Link to="/register">
                    <Button size="sm" className="rounded-lg bg-[#21A038] px-4 font-semibold text-white shadow-sm hover:bg-[#1a8030]">
                        Начать
                    </Button>
                </Link>
            </div>
        </div>
    </header>
)

export const LandingPage = () => {
    return (
        <div className="dark min-h-screen min-w-full scroll-smooth bg-background text-foreground">
            <Header />
            <main>
                <HeroSection />
                <ValueSection />
                <HowItWorksSection />
                <StoriesSection />
                <CTASection />
            </main>
            <Footer />
        </div>
    )
}
