import { Sparkles } from '@artha/design-system'
import { useEffect, useState } from 'react'

import { useMediaQuery } from '../hooks/useMediaQuery'
import { formatMinutes } from '../lib/time'
import type { Plan } from '../lib/types'

/** The reveal's length (PRD 7.3: 600 ms). */
export const REVEAL_MS = 600

/** What the reveal says: "Your first plan is ready: 6 tasks, about 1 h". */
export function revealLine(plan: Pick<Plan, 'counts' | 'planned_minutes'>): string {
  const n = plan.counts.planned
  return `Your first plan is ready: ${n} ${n === 1 ? 'task' : 'tasks'}, about ${formatMinutes(plan.planned_minutes)}`
}

/**
 * Shown once after onboarding hands the student to Today. A 600 ms fade in; with reduced motion or lite mode it is simply there. The
 * moment is the activation event, so the container sends `today_opened` for it.
 */
export function FirstPlanReveal({ plan, lite }: { plan: Plan; lite: boolean }) {
  const reduced = useMediaQuery('(prefers-reduced-motion: reduce)')
  const still = reduced || lite
  const [shown, setShown] = useState(still)
  useEffect(() => {
    if (still) return
    const id = requestAnimationFrame(() => setShown(true))
    return () => cancelAnimationFrame(id)
  }, [still])
  return (
    <section
      role="status"
      aria-label="Your first plan"
      style={still ? undefined : { transition: `opacity ${REVEAL_MS}ms ease-out, transform ${REVEAL_MS}ms ease-out` }}
      className={`flex items-center gap-3 rounded-2xl border border-primary bg-secondary p-4 ${
        shown ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
      }`}
    >
      <Sparkles aria-hidden className="size-6 shrink-0 text-primary" />
      <p className="font-display text-lg font-bold">{revealLine(plan)}</p>
    </section>
  )
}
