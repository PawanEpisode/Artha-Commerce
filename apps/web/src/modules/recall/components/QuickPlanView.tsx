import { ButtonLink, StatTile } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { cutOffSentence, quickSummary } from '../lib/examText'
import { plural } from '../lib/format'
import type { QuickPlan } from '../lib/schemas'
import { QUICK_MINUTE_CHOICES } from '../lib/search'

/** The quick revision plan: what is at risk on exam day, how it fits the daily minutes, and the start button. */
export function QuickPlanView({ plan, minutes }: { plan: QuickPlan; minutes: number }) {
  const cut = cutOffSentence(plan.cut_off)
  return (
    <section
      aria-labelledby="quick-heading"
      className="max-w-3xl space-y-4 rounded-lg border border-border bg-card p-4"
    >
      <div className="space-y-1">
        <h2 id="quick-heading" className="text-base font-semibold">
          {plan.too_few ? 'Your memory looks solid' : `${plural(plan.selected, 'card')} to refresh`}
        </h2>
        <p className="text-[13px] text-muted-foreground">
          {plan.too_few
            ? `Only ${plural(plan.candidates, 'card')} would fade before the exam. Your normal reviews are enough.`
            : quickSummary(plan)}
        </p>
      </div>
      {!plan.too_few ? (
        <div className="grid grid-cols-3 gap-2">
          <StatTile label="Days left" value={plan.days_to_exam} className="p-3 shadow-none" />
          <StatTile label="Per day" value={plan.per_day} className="p-3 shadow-none" />
          <StatTile label="Minutes" value={plan.minutes_per_day} className="p-3 shadow-none" />
        </div>
      ) : null}
      <fieldset className="space-y-2">
        <legend className="text-[13px] font-medium">Minutes you can give each day</legend>
        <div className="flex flex-wrap gap-2">
          {QUICK_MINUTE_CHOICES.map((m) => (
            <ButtonLink key={m} variant={m === minutes ? 'default' : 'outline'} size="sm" asChild>
              <Link to="/app/recall/quick" search={{ minutes: m }} aria-current={m === minutes ? 'true' : undefined}>
                {m} min
              </Link>
            </ButtonLink>
          ))}
        </div>
      </fieldset>
      {cut ? <p className="text-[13px] text-muted-foreground">{cut}</p> : null}
      {!plan.too_few ? (
        <ButtonLink asChild>
          <Link to="/app/recall/review" search={{ source: 'quick' }}>
            Start quick revision
          </Link>
        </ButtonLink>
      ) : null}
    </section>
  )
}
