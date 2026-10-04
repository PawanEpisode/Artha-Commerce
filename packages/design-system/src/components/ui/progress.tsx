import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'

import { cn } from '../../lib/utils'

const clamp = (n: number) => Math.min(100, Math.max(0, Number.isFinite(n) ? n : 0))

const toneClass = {
  primary: 'text-primary',
  destructive: 'text-destructive',
} as const
export type ProgressTone = keyof typeof toneClass

interface ProgressRingProps extends Omit<React.ComponentProps<'div'>, 'children'> {
  /** 0 to 100. */
  value: number
  /** Pixel size of the ring. */
  size?: number
  strokeWidth?: number
  tone?: ProgressTone
  /** Accessible name, e.g. "Overall coverage". The value is announced automatically. */
  label: string
  /** Content inside the ring. Defaults to "{value}%". */
  children?: React.ReactNode
}

/** Circular progress. `role=progressbar` with the numeric value, so meaning is never colour or motion only. */
export function ProgressRing({
  value,
  size = 120,
  strokeWidth = 10,
  tone = 'primary',
  label,
  className,
  children,
  style,
  ...props
}: ProgressRingProps) {
  const v = clamp(value)
  const r = (size - strokeWidth) / 2
  const c = 2 * Math.PI * r
  return (
    <div
      data-slot="progress-ring"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(v)}
      className={cn('relative inline-grid shrink-0 place-items-center', className)}
      style={{ width: size, height: size, ...style }}
      {...props}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={strokeWidth} className="stroke-secondary" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - v / 100)}
          className={cn(
            'stroke-current transition-[stroke-dashoffset] duration-700 ease-out motion-reduce:transition-none',
            toneClass[tone],
          )}
        />
      </svg>
      <span className="absolute inset-0 grid place-items-center font-display text-foreground tabular-nums">
        {children ?? <span className="text-2xl font-bold">{Math.round(v)}%</span>}
      </span>
    </div>
  )
}

const barVariants = cva('h-2 w-full overflow-hidden rounded-full bg-secondary', {
  variants: { size: { sm: 'h-1.5', md: 'h-2', lg: 'h-3' } },
  defaultVariants: { size: 'md' },
})

interface ProgressBarProps extends Omit<React.ComponentProps<'div'>, 'children'>, VariantProps<typeof barVariants> {
  value: number
  tone?: ProgressTone
  label: string
}

const barFill: Record<ProgressTone, string> = {
  primary: 'bg-primary',
  destructive: 'bg-destructive',
}

export function ProgressBar({ value, tone = 'primary', label, size, className, ...props }: ProgressBarProps) {
  const v = clamp(value)
  return (
    <div
      data-slot="progress-bar"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(v)}
      className={cn(barVariants({ size }), className)}
      {...props}
    >
      <div
        className={cn(
          'h-full rounded-full transition-[width] duration-500 ease-out motion-reduce:transition-none',
          barFill[tone],
        )}
        style={{ width: `${v}%` }}
      />
    </div>
  )
}
