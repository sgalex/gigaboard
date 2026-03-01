/**
 * GigaBoard logo: icon mark + optional wordmark.
 * Use on landing (dark) and in app (theme-aware).
 */
import { Link } from 'react-router-dom'

const BRAND_COLOR = '#21A038'

export interface LogoProps {
  /** Show "GigaBoard" text next to the icon */
  showName?: boolean
  /** Wrap in Link to "/" */
  link?: boolean
  /** Optional class for the wrapper */
  className?: string
  /** Icon size in pixels (default 32) */
  size?: number
  /** Variant: 'dark' = light icon/text for dark bg, 'light' = dark for light bg */
  variant?: 'dark' | 'light'
}

export function Logo({
  showName = true,
  link = true,
  className = '',
  size = 32,
  variant = 'dark',
}: LogoProps) {
  const textColor = variant === 'dark' ? 'text-white' : 'text-foreground'
  const content = (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span
        className="flex shrink-0 items-center justify-center rounded-lg"
        style={{ width: size, height: size }}
        aria-hidden
      >
        <svg
          width={size}
          height={size}
          viewBox="0 0 32 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect
            width="32"
            height="32"
            rx="6"
            fill={BRAND_COLOR}
          />
          {/* 2x2 grid = board/canvas */}
          <rect x="6" y="6" width="8" height="8" rx="1" fill="white" fillOpacity="0.95" />
          <rect x="18" y="6" width="8" height="8" rx="1" fill="white" fillOpacity="0.95" />
          <rect x="6" y="18" width="8" height="8" rx="1" fill="white" fillOpacity="0.95" />
          <rect x="18" y="18" width="8" height="8" rx="1" fill="white" fillOpacity="0.95" />
        </svg>
      </span>
      {showName && (
        <span className={`text-xl font-bold tracking-tight ${textColor}`}>
          GigaBoard
        </span>
      )}
    </span>
  )

  if (link) {
    return (
      <Link to="/" className="transition-opacity hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background rounded-md">
        {content}
      </Link>
    )
  }

  return content
}
