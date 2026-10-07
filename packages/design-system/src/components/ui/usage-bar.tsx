import * as React from 'react'

import { CircleAlert } from '../../icons'
import { cn } from '../../lib/utils'

/** `ok` below 90 percent, `near` from 90, `full` at the limit. Words as well as colour. */
export function usageLevel(used: number, limit: number): 'ok' | 'near' | 'full' {
  if (limit <= 0) return 'ok'
  const ratio = used / limit
  if (ratio >= 1) return 'full'
  return ratio >= 0.9 ? 'near' : 'ok'
}

interface UsageBarProps extends Omit<React.ComponentProps<'div'>, 'children'> {
  /** What is measured: "Storage", "Notes". */
  label: string
  used: number
  limit: number
  /** Formats both numbers ("412 MB"). Defaults to en-IN grouping. */
  format?: (value: number) => string
  /** Shown when the limit is reached, for example "Storage full". */
  fullText?: string
}

const defaultFormat = (n: number) => n.toLocaleString('en-IN')

/** A quota meter with the numbers in text ("412 of 500 MB"), so the meaning never rests on the bar's colour. */
export function UsageBar({ label, used, limit, format = defaultFormat, fullText, className, ...props }: UsageBarProps) {
  const level = usageLevel(used, limit)
  const percent = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0
  const text = `${format(used)} of ${format(limit)}`
  return (
    <div data-slot="usage-bar" data-level={level} className={cn('space-y-1.5', className)} {...props}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="text-sm font-semibold">{label}</span>
        <span className="text-sm text-muted-foreground tabular-nums">{text}</span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={Math.min(used, limit)}
        aria-valuetext={text}
        className="h-2 w-full overflow-hidden rounded-full bg-secondary"
      >
        <div
          className={cn(
            'h-full rounded-full transition-[width] duration-500 ease-out motion-reduce:transition-none',
            level === 'ok' && 'bg-primary',
            level === 'near' && 'bg-warning',
            level === 'full' && 'bg-destructive',
          )}
          style={{ width: `${percent}%` }}
        />
      </div>
      {level !== 'ok' ? (
        <p className="flex items-center gap-1.5 text-xs font-medium text-foreground">
          <CircleAlert aria-hidden className="size-3.5 shrink-0" />
          {level === 'full' ? (fullText ?? `${label} full`) : `${label} almost full`}
        </p>
      ) : null}
    </div>
  )
}
