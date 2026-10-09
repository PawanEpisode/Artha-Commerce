import * as React from 'react'

import { cn } from '../../lib/utils'
import { ProgressBar } from './progress'

/** "12 of 30", with the numbers kept inside their range. Empty when there is nothing to do. */
export function counterText(done: number, total: number): string {
  const t = Math.max(0, Math.floor(Number.isFinite(total) ? total : 0))
  if (t === 0) return 'No cards'
  const d = Math.min(Math.max(0, Math.floor(Number.isFinite(done) ? done : 0)), t)
  return `${d} of ${t}`
}

interface ProgressCounterProps extends Omit<React.ComponentProps<'div'>, 'children'> {
  done: number
  total: number
  /** What is being counted, read with the numbers: "Cards reviewed". */
  label: string
}

/**
 * "12 of 30" above a thin bar. The text is a polite live region, so each answered card is announced without stealing focus;
 * the bar carries the same words as its value text. The figures never rely on the bar or on colour.
 */
export function ProgressCounter({ done, total, label, className, ...props }: ProgressCounterProps) {
  const text = counterText(done, total)
  const percent = total > 0 ? (Math.min(Math.max(done, 0), total) / total) * 100 : 0
  return (
    <div data-slot="progress-counter" className={cn('grid gap-1.5', className)} {...props}>
      <p className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium text-muted-foreground">{label}</span>
        <span aria-live="polite" aria-atomic="true" className="font-semibold text-foreground tabular-nums">
          {text}
        </span>
      </p>
      <ProgressBar value={percent} label={label} size="sm" aria-valuetext={text} />
    </div>
  )
}
