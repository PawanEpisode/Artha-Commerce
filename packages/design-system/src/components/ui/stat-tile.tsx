import * as React from 'react'

import { cn } from '../../lib/utils'

interface StatTileProps extends Omit<React.ComponentProps<'div'>, 'children'> {
  label: string
  /** The headline figure, already formatted ("12 h 30 m"). */
  value: React.ReactNode
  /** One line under the value: a comparison, a unit, a hint. Meaning must not rely on colour. */
  hint?: React.ReactNode
}

/** A single headline number with its label. Use it instead of a chart when there is one figure to read. */
export function StatTile({ label, value, hint, className, ...props }: StatTileProps) {
  return (
    <div
      data-slot="stat-tile"
      className={cn('rounded-xl border border-border bg-card p-4 shadow-soft', className)}
      {...props}
    >
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 font-display text-2xl font-bold text-foreground tabular-nums">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}
