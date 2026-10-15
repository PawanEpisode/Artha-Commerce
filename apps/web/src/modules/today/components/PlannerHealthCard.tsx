import { Badge, Button, ProgressBar } from '@artha/design-system'

import { capacityPercent, healthView, nextReplanText, replanSummary, type Tone } from '../lib/planner'
import type { StudyPlan } from '../lib/planner-types'
import { formatDay, formatMinutes } from '../lib/time'

const TONE_CLASS: Record<Tone, string> = {
  good: 'border-accent bg-accent/15',
  warn: 'border-highlight bg-highlight/15',
  bad: 'border-destructive bg-destructive/10',
  quiet: 'border-border bg-card',
}

const Stat = ({ label, value }: { label: string; value: string }) => (
  <div className="min-w-0">
    <dt className="text-xs text-muted-foreground">{label}</dt>
    <dd className="font-medium">{value}</dd>
  </div>
)

/** Health, the numbers behind it, and "Re-plan" (FR-F13-51). The bar is remaining reading against what the days left can hold. */
export function PlannerHealthCard({
  plan,
  replanning,
  onReplan,
}: {
  plan: StudyPlan
  replanning: boolean
  onReplan: () => void
}) {
  const view = healthView(plan)
  const next = nextReplanText(plan)
  return (
    <section
      aria-labelledby="health-heading"
      className={`space-y-4 rounded-2xl border p-4 sm:p-5 ${TONE_CLASS[view.tone]}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="health-heading" className="font-display text-lg font-bold">
          Plan health
        </h2>
        <Badge variant={view.tone === 'good' ? 'accent' : view.tone === 'quiet' ? 'outline' : 'highlight'}>
          {view.label}
        </Badge>
      </div>
      <p className="text-sm">{view.headline}</p>
      <ProgressBar
        value={capacityPercent(plan)}
        tone={plan.health === 'at_risk' ? 'destructive' : 'primary'}
        label="Reading left compared with the time you have for it"
      />
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Stat label="Reading left" value={formatMinutes(plan.remaining_minutes)} />
        <Stat label="Time it fits in" value={formatMinutes(plan.capacity_minutes)} />
        <Stat label="Each day" value={formatMinutes(plan.daily_minutes)} />
        <Stat label="Exam" value={formatDay(plan.exam_date)} />
        {plan.reading_deadline ? <Stat label="Reading done by" value={formatDay(plan.reading_deadline)} /> : null}
      </dl>
      {plan.latest_replan ? <p className="text-sm text-muted-foreground">{replanSummary(plan.latest_replan)}</p> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" onClick={onReplan} disabled={replanning}>
          {replanning ? 'Re-planning' : 'Re-plan'}
        </Button>
        {next ? <span className="text-xs text-muted-foreground">{next}</span> : null}
      </div>
    </section>
  )
}
