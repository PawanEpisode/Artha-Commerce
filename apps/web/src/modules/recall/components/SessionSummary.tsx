import { Alert, StatTile } from '@artha/design-system'
import type { ReactNode } from 'react'

import { minutesLabel, plural } from '../lib/format'

export interface SummaryData {
  reviewed: number
  newCards: number
  ratings: { again: number; hard: number; good: number; easy: number }
  activeSeconds: number
  streakAfter?: number
}

/** How the session went: counts, time and the four answers as numbers and words, never colour only. */
export function SessionSummary({
  data,
  offline,
  actions,
}: {
  data: SummaryData
  offline?: boolean
  actions: ReactNode
}) {
  const { ratings } = data
  const remembered = ratings.good + ratings.easy
  return (
    <section aria-labelledby="summary-heading" className="space-y-5">
      <header className="space-y-1">
        <h1 id="summary-heading" className="font-display text-3xl font-extrabold">
          Session complete
        </h1>
        <p className="text-muted-foreground">
          You reviewed {plural(data.reviewed, 'card')}
          {data.newCards > 0 ? `, ${data.newCards} of them new` : ''}, and remembered {remembered} of them straight
          away.
        </p>
      </header>
      {offline ? (
        <Alert variant="info">
          <span role="status">
            You are offline. This summary is from your device; your reviews will sync when you are back online.
          </span>
        </Alert>
      ) : null}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Again" value={ratings.again} />
        <StatTile label="Hard" value={ratings.hard} />
        <StatTile label="Good" value={ratings.good} />
        <StatTile label="Easy" value={ratings.easy} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <StatTile label="Time" value={minutesLabel(data.activeSeconds)} />
        {data.streakAfter !== undefined ? (
          <StatTile label="Streak" value={plural(data.streakAfter, 'day')} />
        ) : (
          <StatTile label="Streak" value="Updates when synced" />
        )}
      </div>
      <div className="flex flex-wrap gap-3">{actions}</div>
    </section>
  )
}
