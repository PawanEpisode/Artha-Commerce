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
  /** Split the ring into 1 to 12 equal arcs (one per paper, say). Filled arcs = round(value / 100 * segments). */
  segments?: number
  /** Spoken value for a segmented ring, e.g. (filled, total) => `${filled} of ${total} papers done`. */
  segmentLabel?: (filled: number, total: number) => string
}

/** Arcs filled out of `total` for a 0-100 value; a value above zero always lights at least one arc. */
export function filledSegments(value: number, total: number): number {
  const t = Math.min(12, Math.max(1, Math.floor(total)))
  const v = clamp(value)
  const n = Math.round((v / 100) * t)
  return v > 0 ? Math.min(t, Math.max(1, n)) : 0
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
  segments,
  segmentLabel,
  ...props
}: ProgressRingProps) {
  const v = clamp(value)
  const r = (size - strokeWidth) / 2
  const c = 2 * Math.PI * r
  const total = segments === undefined ? 0 : Math.min(12, Math.max(1, Math.floor(segments)))
  const filled = total ? filledSegments(v, total) : 0
  const gap = total > 1 ? Math.min(c / total / 4, strokeWidth * 1.2) : 0
  const arc = total ? c / total - gap : 0
  return (
    <div
      data-slot="progress-ring"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(v)}
      aria-valuetext={total && segmentLabel ? segmentLabel(filled, total) : undefined}
      data-segments={total || undefined}
      className={cn('relative inline-grid shrink-0 place-items-center', className)}
      style={{ width: size, height: size, ...style }}
      {...props}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        {total ? (
          Array.from({ length: total }, (_, i) => (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              strokeWidth={strokeWidth}
              strokeLinecap={total === 1 ? 'round' : 'butt'}
              strokeDasharray={`${arc} ${c - arc}`}
              strokeDashoffset={-(i * (c / total) + gap / 2)}
              data-filled={i < filled ? 'true' : 'false'}
              className={cn(
                'transition-[stroke] duration-500 motion-reduce:transition-none',
                i < filled ? ['stroke-current', toneClass[tone]] : 'stroke-secondary',
              )}
            />
          ))
        ) : (
          <>
            <circle
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              strokeWidth={strokeWidth}
              className="stroke-secondary"
            />
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
          </>
        )}
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
