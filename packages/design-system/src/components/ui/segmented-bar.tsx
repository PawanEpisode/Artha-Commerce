import * as React from 'react'

import { cn } from '../../lib/utils'

export type SegmentVariant = 'primary' | 'success' | 'destructive' | 'warning' | 'muted' | 'accent'

export interface SegmentItem {
  key: string
  value: number
  label: string
  variant?: SegmentVariant
  className?: string
}

export interface SegmentedBarProps {
  segments: SegmentItem[]
  total?: number
  label: string
  showLegend?: boolean
  showValues?: boolean
  height?: 'sm' | 'md' | 'lg'
  className?: string
}

const variantBackgrounds: Record<SegmentVariant, string> = {
  primary: 'bg-primary text-primary-foreground',
  success: 'bg-emerald-600 text-white',
  destructive: 'bg-destructive text-destructive-foreground',
  warning: 'bg-amber-500 text-white',
  muted: 'bg-muted-foreground/30 text-foreground',
  accent: 'bg-indigo-600 text-white',
}

const variantDot: Record<SegmentVariant, string> = {
  primary: 'bg-primary',
  success: 'bg-emerald-600',
  destructive: 'bg-destructive',
  warning: 'bg-amber-500',
  muted: 'bg-muted-foreground/50',
  accent: 'bg-indigo-600',
}

export function SegmentedBar({
  segments,
  total: totalProp,
  label,
  showLegend = false,
  showValues = false,
  height = 'md',
  className,
}: SegmentedBarProps) {
  const sumValues = React.useMemo(() => segments.reduce((acc, s) => acc + (s.value > 0 ? s.value : 0), 0), [segments])
  const total = totalProp !== undefined ? totalProp : Math.max(1, sumValues)

  const textSummary = segments
    .filter((s) => s.value > 0)
    .map((s) => `${s.value} ${s.label}`)
    .join(', ')

  return (
    <div className={cn('w-full space-y-2', className)}>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={sumValues}
        aria-valuetext={textSummary || 'No data'}
        className={cn(
          'flex w-full overflow-hidden rounded-full bg-muted/40 shadow-inner',
          height === 'sm' && 'h-2',
          height === 'md' && 'h-3.5',
          height === 'lg' && 'h-5',
        )}
      >
        {sumValues === 0 ? (
          <div className="h-full w-full bg-muted/50" />
        ) : (
          segments.map((seg) => {
            if (seg.value <= 0) return null
            const pct = Math.min(100, Math.max(0, (seg.value / total) * 100))
            const variant = seg.variant ?? 'primary'
            return (
              <div
                key={seg.key}
                style={{ width: `${pct}%` }}
                title={`${seg.label}: ${seg.value} (${Math.round(pct)}%)`}
                className={cn('h-full transition-all duration-300', variantBackgrounds[variant], seg.className)}
              />
            )
          })
        )}
      </div>

      {showLegend && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
          {segments.map((seg) => {
            const variant = seg.variant ?? 'primary'
            return (
              <div key={seg.key} className="flex items-center gap-1.5">
                <span className={cn('size-2 shrink-0 rounded-full', variantDot[variant])} aria-hidden />
                <span className="font-medium text-foreground">{seg.label}</span>
                {showValues && <span className="font-mono text-muted-foreground tabular-nums">({seg.value})</span>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
