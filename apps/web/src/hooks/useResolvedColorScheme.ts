import { useEffect, useState } from 'react'
import { useTheme } from '@/components/ThemeProvider'

/**
 * Текущая светлая/тёмная схема так же, как у класса на `document.documentElement`
 * (см. ThemeProvider: dark | light | system).
 */
export function useResolvedColorScheme(): 'light' | 'dark' {
    const { theme } = useTheme()
    const [systemIsDark, setSystemIsDark] = useState(() =>
        typeof window !== 'undefined'
            ? window.matchMedia('(prefers-color-scheme: dark)').matches
            : false
    )

    useEffect(() => {
        if (theme !== 'system') return
        const mq = window.matchMedia('(prefers-color-scheme: dark)')
        const onChange = () => setSystemIsDark(mq.matches)
        onChange()
        mq.addEventListener('change', onChange)
        return () => mq.removeEventListener('change', onChange)
    }, [theme])

    if (theme === 'dark') return 'dark'
    if (theme === 'light') return 'light'
    return systemIsDark ? 'dark' : 'light'
}
