import { Celebrate, CircleCheck, Sparkles } from '@artha/design-system'

import { formatMinutes } from '../lib/time'
import type { Plan } from '../lib/types'

/**
 * The day's close. `celebrate`: a short burst the first time (any device), then a quiet card. `calm`: no confetti, a kind line.
 * `burst` is true only in the moment the plan said "show it".
 */
export function CelebrationCard({ plan, burst, lite = false }: { plan: Plan; burst: boolean; lite?: boolean }) {
  const { done, skipped } = plan.counts
  if (plan.closing === 'celebrate') {
    return (
      <section
        aria-labelledby="celebrate-heading"
        className="space-y-0.5 rounded-lg border border-primary bg-secondary p-3 text-center"
      >
        <CircleCheck aria-hidden className="mx-auto size-6 text-success" />
        <h2 id="celebrate-heading" className="text-sm font-semibold">
          Day complete
        </h2>
        <p className="text-[13px]">
          {done} of {plan.counts.planned} done · {formatMinutes(plan.planned_minutes)} planned
        </p>
        <Celebrate active={burst && !lite} message="Day complete. Well done." className="sr-only" />
      </section>
    )
  }
  if (plan.closing === 'calm') {
    return (
      <section
        aria-labelledby="calm-heading"
        className="space-y-0.5 rounded-lg border border-border bg-card p-3 text-center"
      >
        <Sparkles aria-hidden className="mx-auto size-5 text-primary" />
        <h2 id="calm-heading" className="text-sm font-semibold">
          Day closed
        </h2>
        <p className="text-[13px] text-muted-foreground">
          You did {done} and skipped {skipped}. Tomorrow is a fresh start.
        </p>
      </section>
    )
  }
  return null
}
