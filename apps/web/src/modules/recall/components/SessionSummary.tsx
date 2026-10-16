import { Alert, PageHeader, StatTile } from '@artha/design-system'
import type { ReactNode } from 'react'

import { minutesLabel, plural } from '../lib/format'

export interface SummaryData {
  reviewed: number
  newCards: number
  ratings: { again: number; hard: number; good: number; easy: number }
  activeSeconds: number
  streakAfter?: number
}

/** How the session went: one row of figures (the four answers as numbers and words, never colour only, then time and streak). */
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
    <section aria-label="Session summary" className="space-y-4">
      <PageHeader
        title="Session complete"
        description={`You reviewed ${plural(data.reviewed, 'card')}${
          data.newCards > 0 ? `, ${data.newCards} of them new` : ''
        }, and remembered ${remembered} of them straight away.`}
        actions={actions}
      />
      {offline ? (
        <Alert variant="info">
          <span role="status">
            You are offline. This summary is from your device; your reviews will sync when you are back online.
          </span>
        </Alert>
      ) : null}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Again" value={ratings.again} className="p-3" />
        <StatTile label="Hard" value={ratings.hard} className="p-3" />
        <StatTile label="Good" value={ratings.good} className="p-3" />
        <StatTile label="Easy" value={ratings.easy} className="p-3" />
        <StatTile label="Time" value={minutesLabel(data.activeSeconds)} className="p-3" />
        {data.streakAfter !== undefined ? (
          <StatTile label="Streak" value={plural(data.streakAfter, 'day')} className="p-3" />
        ) : (
          <StatTile label="Streak" value="Updates when synced" className="p-3" />
        )}
      </div>
    </section>
  )
}
