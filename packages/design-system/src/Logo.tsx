import { cn } from './lib/utils'

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn('size-8', className)}>
      <rect width="32" height="32" rx="9" className="fill-primary" />
      <path
        d="M9 22 16 8l7 14"
        fill="none"
        stroke="white"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M12 18h8" stroke="oklch(0.83 0.15 78)" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  )
}

/** `compactOnMobile` shows only the mark below 640 px (the name stays available to screen readers). */
export function Logo({ className, compactOnMobile = false }: { className?: string; compactOnMobile?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5 font-display text-lg font-bold tracking-tight', className)}>
      <LogoMark />
      <span className={cn(compactOnMobile && 'max-sm:sr-only')}>
        Artha<span className="text-primary">Commerce</span>
      </span>
    </span>
  )
}
