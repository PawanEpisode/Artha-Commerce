import { Button, Flame, ProgressBar, ProgressRing } from '@artha/design-system'

import { minutesLeft } from '../lib/optimistic'
import { starterTask, taskCountLabel } from '../lib/plan'
import { dayPart, examCountdown, formatDay, formatMinutes, greeting, hourIn } from '../lib/time'
import type { Plan, Task } from '../lib/types'

const AT_RISK_HOUR = 18

/** Greeting, the segmented ring ("3 of 6 done · about 35 min left"), streak, the tracker's goal, and the one starter action. */
export function TodayHeader({
  plan,
  firstName,
  onStart,
  lite = false,
}: {
  plan: Plan
  firstName?: string | null
  onStart?: (task: Task) => void
  /** Lite mode: no ring and no goal bar, a smaller heading. */
  lite?: boolean
}) {
  const starter = starterTask(plan)
  const { planned, done } = plan.counts
  const percent = planned ? (done / planned) * 100 : 0
  const exam = examCountdown(plan.days_to_exam)
  const hour = hourIn(plan.server_time, plan.tz)
  const left = minutesLeft(plan)
  const goal = plan.goal && plan.goal.target_minutes > 0 ? plan.goal : null
  const goalMet = goal ? goal.percent >= 100 : false
  const comeback = plan.budget_source === 'comeback'
  return (
    <header className="space-y-4 rounded-2xl border border-border bg-card p-4 shadow-soft sm:p-6">
      <div className="flex flex-wrap items-center gap-5">
        {lite ? null : (
          <ProgressRing
            value={percent}
            size={96}
            strokeWidth={9}
            segments={planned > 0 ? Math.min(12, planned) : undefined}
            segmentLabel={taskCountLabel}
            label="Today's tasks"
          >
            <span className="text-center leading-tight">
              <span className="block text-lg font-bold">
                {done}/{planned}
              </span>
              <span className="block text-[11px] text-muted-foreground">tasks</span>
            </span>
          </ProgressRing>
        )}
        <div className="min-w-0 flex-1 space-y-1">
          <h1 className={`font-display font-extrabold ${lite ? 'text-xl' : 'text-2xl sm:text-3xl'}`}>
            {comeback ? `Welcome back${firstName ? `, ${firstName}` : ''}` : greeting(dayPart(hour), firstName)}
          </h1>
          {comeback ? <p className="text-sm font-medium">A lighter day to ease back in.</p> : null}
          <p className="text-sm text-muted-foreground">
            {formatDay(plan.date)} · {done} of {planned} done
            {left > 0 ? ` · about ${formatMinutes(left)} left` : ''}
            {exam ? ` · ${exam}` : ''}
          </p>
          {plan.streak > 0 ? (
            <p className="flex items-center gap-1.5 text-sm font-medium">
              <Flame aria-hidden className="size-4 text-primary" />
              {plan.streak === 1 ? '1 day streak' : `${plan.streak} day streak`}
            </p>
          ) : null}
        </div>
      </div>
      {goal && !lite ? (
        <div className="space-y-1">
          <ProgressBar value={goal.percent} size="sm" label="Daily study goal" />
          <p className="text-xs text-muted-foreground">
            Goal {formatMinutes(goal.target_minutes)}: {formatMinutes(goal.done_seconds / 60)} studied
            {plan.streak > 0 && !goalMet && hour >= AT_RISK_HOUR
              ? '. A little study tonight keeps your streak going.'
              : ''}
          </p>
        </div>
      ) : null}
      {starter?.link ? (
        <Button variant="cta" size="lg" className="w-full sm:w-auto" onClick={() => onStart?.(starter)}>
          {starter.state === 'accepted' ? 'Continue' : 'Start here'}: {starter.title}
        </Button>
      ) : null}
    </header>
  )
}
