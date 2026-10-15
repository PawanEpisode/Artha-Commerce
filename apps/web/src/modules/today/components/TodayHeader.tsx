import { Button, Flame, ProgressRing } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { starterTask, taskCountLabel } from '../lib/plan'
import { dayPart, examCountdown, formatDay, formatMinutes, greeting, hourIn } from '../lib/time'
import type { Plan } from '../lib/types'

/** Greeting, the day's ring, minutes, streak, and the one "Start here" action. */
export function TodayHeader({ plan, firstName }: { plan: Plan; firstName?: string | null }) {
  const starter = starterTask(plan)
  const { planned, done } = plan.counts
  const percent = planned ? (done / planned) * 100 : 0
  const exam = examCountdown(plan.days_to_exam)
  const streak = plan.streak?.current ?? 0
  return (
    <header className="flex flex-wrap items-center gap-5 rounded-2xl border border-border bg-card p-4 shadow-soft sm:p-6">
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
      <div className="min-w-0 flex-1 space-y-1">
        <h1 className="font-display text-2xl font-extrabold sm:text-3xl">
          {greeting(dayPart(hourIn(plan.server_time, plan.tz)), firstName)}
        </h1>
        <p className="text-sm text-muted-foreground">
          {formatDay(plan.date)} · about {formatMinutes(plan.planned_minutes)} of {formatMinutes(plan.budget_minutes)}
          {exam ? ` · ${exam}` : ''}
        </p>
        {streak > 0 ? (
          <p className="flex items-center gap-1.5 text-sm font-medium">
            <Flame aria-hidden className="size-4 text-primary" />
            {streak === 1 ? '1 day streak' : `${streak} day streak`}
          </p>
        ) : null}
      </div>
      {starter?.link ? (
        <Button asChild variant="cta" size="lg" className="w-full sm:w-auto">
          <Link to={starter.link.path as never} search={starter.link.search as never}>
            Start here: {starter.title}
          </Link>
        </Button>
      ) : null}
    </header>
  )
}
