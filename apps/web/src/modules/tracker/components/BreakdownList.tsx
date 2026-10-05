import { ProgressBar } from '@artha/design-system'

import { formatDuration } from '../lib/duration'
import type { Breakdown } from '../lib/types'

/** Share of time per subject or activity: a bar, the time and the percentage in words. */
export function BreakdownList({ title, data }: { title: string; data: Breakdown }) {
  return (
    <section aria-label={title} className="space-y-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {data.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No study time in this range.</p>
      ) : (
        <ul className="space-y-3">
          {data.items.map((item) => (
            <li key={item.key} className="space-y-1">
              <p className="flex justify-between gap-3 text-sm">
                <span className="font-medium">{item.name}</span>
                <span className="text-muted-foreground tabular-nums">
                  {formatDuration(item.seconds)} · {Math.round(item.share_percent)}%
                </span>
              </p>
              <ProgressBar value={item.share_percent} label={`${item.name} share of time`} size="sm" />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
