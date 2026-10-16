import { Flame, StatTile } from '@artha/design-system'
import type { ReactNode } from 'react'

import { estimate, plural } from '../lib/format'
import type { TodayPlan } from '../lib/schemas'

/** Today's session: the size and time on the left, the start button on the right, three figures underneath. */
export function QueueSummary({ plan, action }: { plan: TodayPlan; action: ReactNode }) {
  return (
    <section aria-labelledby="today-heading" className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h2 id="today-heading" className="text-base font-semibold">
            {plural(plan.queue_size, 'card')} for today
          </h2>
          <p className="text-[13px] text-muted-foreground">{estimate(plan.est_minutes)}</p>
        </div>
        {action}
      </div>
      <div className="grid grid-cols-3 gap-2">
        <StatTile label="New" value={plan.counts.new} className="p-3 shadow-none" />
        <StatTile label="Learning" value={plan.counts.learning} className="p-3 shadow-none" />
        <StatTile label="Review" value={plan.counts.due} className="p-3 shadow-none" />
      </div>
      {plan.streak > 0 ? (
        <p className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
          <Flame className="size-3.5" aria-hidden />
          {plural(plan.streak, 'day')} in a row
        </p>
      ) : null}
    </section>
  )
}
