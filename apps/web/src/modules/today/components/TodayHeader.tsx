import { Button, Flame, PageHeader, ProgressBar, ProgressRing } from '@artha/design-system'

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
    <div className="space-y-3">
      <PageHeader
        title={comeback ? `Welcome back${firstName ? `, ${firstName}` : ''}` : greeting(dayPart(hour), firstName)}
        description={
          <>
            {comeback ? (
              <span className="block font-medium text-foreground">A lighter day to ease back in.</span>
            ) : null}
            {formatDay(plan.date)} · {done} of {planned} done
            {left > 0 ? ` · about ${formatMinutes(left)} left` : ''}
            {exam ? ` · ${exam}` : ''}
          </>
        }
      />
      {lite && plan.streak === 0 && !starter?.link ? null : (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border bg-card px-3 py-2.5 shadow-soft">
          {lite ? null : (
            <ProgressRing
              value={percent}
              size={48}
              strokeWidth={6}
              segments={planned > 0 ? Math.min(12, planned) : undefined}
              segmentLabel={taskCountLabel}
              label="Today's tasks"
            >
              <span className="text-center text-xs leading-tight font-semibold">
                {done}/{planned}
              </span>
            </ProgressRing>
          )}
          {plan.streak > 0 ? (
            <p className="flex items-center gap-1.5 text-[13px] font-medium">
              <Flame aria-hidden className="size-4 text-primary" />
              {plan.streak === 1 ? '1 day streak' : `${plan.streak} day streak`}
            </p>
          ) : null}
          {goal && !lite ? (
            <div className="min-w-[10rem] flex-1 space-y-1">
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
            <Button
              variant="cta"
              size="sm"
              className="h-auto max-w-full py-1.5 text-left whitespace-normal sm:ml-auto"
              onClick={() => onStart?.(starter)}
            >
              {starter.state === 'accepted' ? 'Continue' : 'Start here'}: {starter.title}
            </Button>
          ) : null}
        </div>
      )}
    </div>
  )
}
