import {
  addIsoDays,
  Alert,
  ArrowLeft,
  ArrowRight,
  Button,
  EmptyState,
  isIsoDate,
  Page,
  PageHeader,
  Skeleton,
} from '@artha/design-system'
import { Link, Navigate } from '@tanstack/react-router'

import { TaskRow } from '../components/TaskRow'
import { useTodayFlag } from '../hooks/useTodayFlag'
import { useDayPlan, useDayPreview, useTodayPlan } from '../hooks/useTodayQueries'
import { errorCode } from '../lib/api'
import { PREVIEW_MAX_DAYS_AHEAD } from '../lib/limits'
import { groupTasks } from '../lib/plan'
import { formatDay, formatMinutes } from '../lib/time'

const Shell = ({ children }: { children: React.ReactNode }) => <Page width="reading">{children}</Page>

const daysBetween = (from: string, to: string) =>
  Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000)

function Nav({ date, today }: { date: string; today: string }) {
  const prev = addIsoDays(date, -1)
  const next = addIsoDays(date, 1)
  const link =
    'inline-flex min-h-8 items-center gap-1 text-[13px] font-medium underline-offset-4 hover:underline pointer-coarse:min-h-11'
  const to = (d: string) => (d === today ? '/app/today' : '/app/today/$date')
  return (
    <nav aria-label="Day" className="flex items-center justify-between">
      <Link to={to(prev) as never} params={{ date: prev } as never} className={link}>
        <ArrowLeft aria-hidden className="size-4" /> {formatDay(prev)}
      </Link>
      <Link to="/app/today" className={link}>
        Today
      </Link>
      <Link to={to(next) as never} params={{ date: next } as never} className={link}>
        {formatDay(next)} <ArrowRight aria-hidden className="size-4" />
      </Link>
    </nav>
  )
}

const NoPlan = () => (
  <EmptyState
    title="No plan for this day"
    description="Nothing was planned for it."
    action={
      <Button asChild variant="outline">
        <Link to="/app/today">Back to today</Link>
      </Button>
    }
  />
)

/** `/app/today/$date`: tomorrow's preview ("may change"), a past day's read-only recap, or "no plan". Today redirects to `/app/today`. */
export function DayViewContainer({ date }: { date: string }) {
  const enabled = useTodayFlag()
  const todayPlan = useTodayPlan(enabled)
  const valid = isIsoDate(date)
  const today = todayPlan.data?.date ?? null
  const offset = today && valid ? daysBetween(today, date) : null
  const preview = useDayPreview(offset !== null && offset > 0 && offset <= PREVIEW_MAX_DAYS_AHEAD ? date : null)
  const past = useDayPlan(offset !== null && offset < 0 ? date : null)

  if (!enabled)
    return (
      <Shell>
        <EmptyState title="Today is not available yet" description="We are rolling it out gradually." />
      </Shell>
    )
  if (!valid)
    return (
      <Shell>
        <NoPlan />
      </Shell>
    )
  if (todayPlan.isPending || !today)
    return (
      <Shell>
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-24 w-full" />
      </Shell>
    )
  if (offset === 0) return <Navigate to="/app/today" search={{}} replace />

  let body: React.ReactNode
  if (offset !== null && offset > 0) {
    if (offset > PREVIEW_MAX_DAYS_AHEAD) body = <NoPlan />
    else if (preview.isPending) body = <Skeleton className="h-24 w-full" />
    else if (preview.isError || !preview.data) body = <NoPlan />
    else {
      const p = preview.data
      const items = [
        ...p.tasks.map((t) => ({ key: `${t.kind}-${t.title}`, title: t.title, minutes: t.est_minutes })),
        ...p.own_tasks.map((t) => ({ key: t.id, title: t.title, minutes: t.est_minutes })),
      ]
      body = (
        <>
          <Alert variant="info">Preview, may change. Nothing here is saved until the day starts.</Alert>
          {items.length ? (
            <ul className="divide-y overflow-hidden rounded-lg border bg-card">
              {items.map((i) => (
                <li key={i.key} className="flex items-start justify-between gap-3 px-3 py-2">
                  <span className="min-w-0 font-medium break-words">{i.title}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{formatMinutes(i.minutes)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <NoPlan />
          )}
        </>
      )
    }
  } else if (past.isPending) body = <Skeleton className="h-24 w-full" />
  else if (past.isError || !past.data)
    body = errorCode(past.error) === 'plan_not_generated' || past.isError ? <NoPlan /> : null
  else {
    const plan = past.data
    const g = groupTasks(plan.tasks)
    body = (
      <>
        <Alert variant="info">
          Recap: {plan.counts.done} of {plan.counts.planned} done.
        </Alert>
        <ul className="divide-y overflow-hidden rounded-lg border bg-card">
          {[...g.done, ...g.open, ...g.parked].map((t) => (
            <TaskRow key={t.id} task={t} readOnly />
          ))}
        </ul>
      </>
    )
  }

  return (
    <Shell>
      <PageHeader title={formatDay(date)} />
      <Nav date={date} today={today} />
      {body}
    </Shell>
  )
}
