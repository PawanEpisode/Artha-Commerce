import { Button } from '@artha/design-system'
import type { ReactNode } from 'react'

import { backlogSentence } from '../lib/format'
import type { TodayPlan } from '../lib/schemas'

/**
 * Said kindly: a backlog is days of work at your own pace, never a red number. New cards pause until you are back on
 * track, and the student can spread the backlog over the coming days.
 */
export function CatchUpNotice({
  plan,
  action,
  onRebalance,
  rebalancing,
}: {
  plan: TodayPlan
  action: ReactNode
  onRebalance: () => void
  rebalancing: boolean
}) {
  return (
    <section
      aria-labelledby="catchup-heading"
      className="space-y-4 rounded-2xl border border-info-border bg-info-bg p-5 text-info-fg"
    >
      <div className="space-y-1">
        <h2 id="catchup-heading" className="font-display text-xl font-bold">
          Let's get you back on track
        </h2>
        <p className="text-sm">
          {backlogSentence(plan.catchup.due, plan.days_to_clear)} Today you will see the {plan.queue_size} most
          important and most overdue cards. New cards wait until you are caught up.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {action}
        <Button variant="outline" onClick={onRebalance} disabled={rebalancing} aria-busy={rebalancing}>
          Spread it over the next 7 days
        </Button>
      </div>
    </section>
  )
}
