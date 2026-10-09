import { Flame, StatTile } from '@artha/design-system'
import type { ReactNode } from 'react'

import { estimate, plural } from '../lib/format'
import type { TodayPlan } from '../lib/schemas'

/** Today's session in three small figures, the time it should take and the streak. The start button is passed in. */
export function QueueSummary({ plan, action }: { plan: TodayPlan; action: ReactNode }) {
  return (
    <section
      aria-labelledby="today-heading"
      className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-soft"
    >
      <div className="space-y-1">
        <h2 id="today-heading" className="font-display text-xl font-bold">
          {plural(plan.queue_size, 'card')} for today
        </h2>
        <p className="text-sm text-muted-foreground">{estimate(plan.est_minutes)}</p>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <StatTile label="New" value={plan.counts.new} />
        <StatTile label="Learning" value={plan.counts.learning} />
        <StatTile label="Review" value={plan.counts.due} />
      </div>
      {plan.streak > 0 ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Flame className="size-4" aria-hidden />
          {plural(plan.streak, 'day')} in a row
        </p>
      ) : null}
      {action}
    </section>
  )
}
