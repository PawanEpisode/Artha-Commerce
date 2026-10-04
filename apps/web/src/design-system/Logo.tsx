import { cn } from '~/lib/utils'

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn('size-8', className)}>
      <rect width="32" height="32" rx="9" className="fill-primary" />
      <path d="M9 22 16 8l7 14" fill="none" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 18h8" stroke="oklch(0.83 0.15 78)" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  )
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5 font-display text-lg font-bold tracking-tight', className)}>
      <LogoMark />
      <span>
        Artha<span className="text-primary">Commerce</span>
      </span>
    </span>
  )
}
