import { ReactNode } from "react"
import { ThemeToggle } from "./ThemeToggle"
import { Logo } from "./Logo"

interface AuthLayoutProps {
    title: string
    subtitle: string
    children: ReactNode
    footer?: ReactNode
}

export const AuthLayout = ({
    title,
    subtitle,
    children,
    footer,
}: AuthLayoutProps) => {
    return (
        <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12 sm:px-6 lg:px-8 transition-colors duration-300">
            <div className="absolute right-4 top-4">
                <ThemeToggle />
            </div>
            <div className="w-full max-w-[440px] space-y-8">
                <div className="flex flex-col items-center">
                    <Logo showName link variant="light" size={48} className="mb-2" />
                    <h2 className="mt-6 text-center text-4xl font-bold tracking-tight text-foreground">
                        {title}
                    </h2>
                    <p className="mt-3 text-center text-base text-muted-foreground">
                        {subtitle}
                    </p>
                </div>

                <div className="mt-8 rounded-[32px] border border-border bg-card/80 p-10 shadow-2xl backdrop-blur-xl transition-all">
                    <div className="space-y-6">
                        {children}
                    </div>

                    {footer && (
                        <div className="mt-10 border-t border-border pt-8 text-center text-sm text-muted-foreground">
                            {footer}
                        </div>
                    )}
                </div>

                <p className="text-center text-xs text-muted-foreground">
                    &copy; {new Date().getFullYear()} GigaBoard Inc. Все права защищены.
                </p>
            </div>
        </div>
    )
}
