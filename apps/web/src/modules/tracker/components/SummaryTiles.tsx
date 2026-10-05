import { StatTile } from '@artha/design-system'

import { formatDuration } from '../lib/duration'
import { dayLabel } from '../lib/format'
import type { Summary } from '../lib/types'

function changeHint(summary: Summary): string | undefined {
  const c = summary.change
  if (!c || !summary.previous) return undefined
  const sign = c.delta_seconds > 0 ? 'up' : c.delta_seconds < 0 ? 'down' : 'same as'
  if (sign === 'same as') return 'Same as the previous period'
  const pct = c.percent === null ? '' : ` (${Math.abs(Math.round(c.percent))}%)`
  return `${sign === 'up' ? 'Up' : 'Down'} ${formatDuration(Math.abs(c.delta_seconds))}${pct} on the previous period`
}

/** The headline numbers of a range. The change is written out, so it never depends on colour. */
export function SummaryTiles({ summary }: { summary: Summary }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile label="Total study time" value={formatDuration(summary.total_seconds)} hint={changeHint(summary)} />
      <StatTile
        label="Days studied"
        value={summary.days_studied}
        hint={
          summary.days_studied
            ? `${formatDuration(summary.average_seconds_per_studied_day)} on an average day`
            : undefined
        }
      />
      <StatTile
        label="Best day"
        value={summary.longest_day ? formatDuration(summary.longest_day.seconds) : '0 m'}
        hint={summary.longest_day ? dayLabel(summary.longest_day.date) : undefined}
      />
      <StatTile
        label="Sessions"
        value={summary.sessions}
        hint={summary.sessions ? `Longest ${formatDuration(summary.longest_session_seconds)}` : undefined}
      />
    </div>
  )
}
