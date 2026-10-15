import { Celebrate, CircleCheck, Sparkles } from '@artha/design-system'

import { formatMinutes } from '../lib/time'
import type { Plan } from '../lib/types'

/**
 * The day's close. `celebrate`: a short burst the first time (any device), then a quiet card. `calm`: no confetti, a kind line.
 * `burst` is true only in the moment the plan said "show it".
 */
export function CelebrationCard({ plan, burst }: { plan: Plan; burst: boolean }) {
  const { done, skipped } = plan.counts
  if (plan.closing === 'celebrate') {
    return (
      <section
        aria-labelledby="celebrate-heading"
        className="space-y-1 rounded-2xl border border-primary bg-secondary p-5 text-center"
      >
        <CircleCheck aria-hidden className="mx-auto size-10 text-success" />
        <h2 id="celebrate-heading" className="font-display text-xl font-extrabold">
          Day complete
        </h2>
        <p className="text-sm">
          {done} of {plan.counts.planned} done · {formatMinutes(plan.planned_minutes)} planned
        </p>
        <Celebrate active={burst} message="Day complete. Well done." className="sr-only" />
      </section>
    )
  }
  if (plan.closing === 'calm') {
    return (
      <section
        aria-labelledby="calm-heading"
        className="space-y-1 rounded-2xl border border-border bg-card p-5 text-center"
      >
        <Sparkles aria-hidden className="mx-auto size-8 text-primary" />
        <h2 id="calm-heading" className="font-display text-lg font-bold">
          Day closed
        </h2>
        <p className="text-sm text-muted-foreground">
          You did {done} and skipped {skipped}. Tomorrow is a fresh start.
        </p>
      </section>
    )
  }
  return null
}
