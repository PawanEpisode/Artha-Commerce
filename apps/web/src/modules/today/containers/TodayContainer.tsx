import {
  Alert,
  Button,
  CalendarClock,
  Celebrate,
  Container,
  EmptyState,
  Info,
  Skeleton,
  Sparkles,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'

import { useBootstrap } from '~/modules/personalization'

import { PaperTile } from '../components/PaperTile'
import { TaskRow } from '../components/TaskRow'
import { TodayHeader } from '../components/TodayHeader'
import { useTodayFlag } from '../hooks/useTodayFlag'
import { useTodayPlan } from '../hooks/useTodayQueries'
import { isFeatureDisabled } from '../lib/api'
import { groupTasks, screenState, selectedTile, tileViews } from '../lib/plan'
import type { TodaySearch } from '../lib/search'
import { isEmptyPlan, type Plan } from '../lib/types'

const Shell = ({ children }: { children: React.ReactNode }) => (
  <Container className="max-w-3xl min-w-0 space-y-5 py-6 sm:space-y-6 sm:py-10">{children}</Container>
)

function Loading() {
  return (
    <Shell>
      <div role="status" aria-label="Loading today's plan" className="space-y-4">
        <Skeleton className="h-32 w-full rounded-2xl" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Skeleton className="h-20 rounded-xl" />
          <Skeleton className="h-20 rounded-xl" />
          <Skeleton className="hidden h-20 rounded-xl sm:block" />
        </div>
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-16 w-full rounded-xl" />
      </div>
    </Shell>
  )
}

function Unavailable() {
  return (
    <Shell>
      <EmptyState
        icon={<Sparkles aria-hidden />}
        title="Today is not available yet"
        description="We are rolling it out gradually. Please check back soon."
        action={
          <Button asChild variant="outline">
            <Link to="/app" search={{ from: undefined, home: true }}>
              Back to your workspace
            </Link>
          </Button>
        }
      />
    </Shell>
  )
}

function Body({ plan, search, firstName }: { plan: Plan; search: TodaySearch; firstName?: string | null }) {
  const navigate = useNavigate({ from: '/app/today' })
  const state = screenState(plan)
  const views = tileViews(plan)
  const chosen = selectedTile(views, search.paper)
  const groups = groupTasks(chosen ? chosen.tasks : plan.tasks)
  const choose = (key: string | undefined) =>
    void navigate({ search: (prev) => ({ ...prev, paper: key }), replace: true, resetScroll: false })

  return (
    <Shell>
      <TodayHeader plan={plan} firstName={firstName} />
      {plan.partial ? (
        <Alert variant="info">
          Some suggestions are missing right now, so today's list may be shorter than usual. Reload in a moment to try
          again.
        </Alert>
      ) : null}
      <Celebrate
        active={state === 'all_done' && plan.celebrate}
        message="Day complete. Well done."
        className="text-center font-display text-lg font-bold empty:hidden"
      />
      {state === 'all_done' ? (
        <Alert variant="success">You finished today's plan. Anything left below is optional.</Alert>
      ) : null}

      {state === 'nothing_due' ? (
        <EmptyState
          icon={<CalendarClock aria-hidden />}
          title="Nothing is due today"
          description="You are caught up. Pick something from your syllabus if you want to get ahead."
          action={
            <Button asChild variant="outline">
              <Link to="/app/syllabus">Open your syllabus</Link>
            </Button>
          }
        />
      ) : (
        <>
          {views.length > 1 ? (
            <section aria-label="Papers" className="space-y-2">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {views.map((tile) => (
                  <PaperTile
                    key={tile.key}
                    tile={tile}
                    pressed={chosen?.key === tile.key}
                    onSelect={() => choose(chosen?.key === tile.key ? undefined : tile.key)}
                  />
                ))}
              </div>
              {chosen ? (
                <Button variant="ghost" size="sm" onClick={() => choose(undefined)}>
                  Show all papers
                </Button>
              ) : null}
            </section>
          ) : null}

          <section aria-labelledby="open-tasks" className="space-y-3">
            <h2 id="open-tasks" className="font-display text-lg font-bold">
              {groups.open.length ? 'To do' : 'Nothing left to do'}
            </h2>
            <ul className="space-y-2">
              {groups.open.map((t) => (
                <TaskRow key={t.id} task={t} highlighted={search.task === t.id} />
              ))}
            </ul>
          </section>

          {groups.done.length ? (
            <section aria-labelledby="done-tasks" className="space-y-3">
              <h2 id="done-tasks" className="font-display text-lg font-bold">
                Done
              </h2>
              <ul className="space-y-2">
                {groups.done.map((t) => (
                  <TaskRow key={t.id} task={t} highlighted={search.task === t.id} />
                ))}
              </ul>
            </section>
          ) : null}

          {groups.parked.length ? (
            <section aria-labelledby="parked-tasks" className="space-y-3">
              <h2 id="parked-tasks" className="font-display text-lg font-bold text-muted-foreground">
                Skipped and snoozed
              </h2>
              <ul className="space-y-2">
                {groups.parked.map((t) => (
                  <TaskRow key={t.id} task={t} highlighted={search.task === t.id} />
                ))}
              </ul>
            </section>
          ) : null}
        </>
      )}

      {plan.backlog.length ? (
        <section aria-labelledby="backlog" className="space-y-2">
          <h2 id="backlog" className="font-display text-lg font-bold">
            Waiting for you
          </h2>
          <ul className="space-y-1 text-sm">
            {plan.backlog.map((b) => (
              <li key={b.kind} className="flex items-center gap-2">
                <Info aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                {b.link ? (
                  <Link
                    to={b.link.path as never}
                    search={b.link.search as never}
                    className="underline-offset-4 hover:underline"
                  >
                    {b.label}
                  </Link>
                ) : (
                  <span>{b.label}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </Shell>
  )
}

/** /app/today (PRD 7.3). Gate on the flag, open today's plan, then show the right state. Actions arrive in W5. */
export function TodayContainer({ search }: { search: TodaySearch }) {
  const enabled = useTodayFlag()
  const bootstrap = useBootstrap()
  const plan = useTodayPlan(enabled)

  if (!enabled || isFeatureDisabled(plan.error)) return <Unavailable />
  if (plan.isPending) return <Loading />
  if (plan.isError || !plan.data) {
    return (
      <Shell>
        <Alert variant="error">
          <p>We could not load today's plan.</p>
          <Button className="mt-3" variant="outline" size="sm" onClick={() => void plan.refetch()}>
            Try again
          </Button>
        </Alert>
      </Shell>
    )
  }
  const data = plan.data
  if (isEmptyPlan(data)) {
    return (
      <Shell>
        {data.state === 'post_exam' ? (
          <EmptyState
            icon={<CalendarClock aria-hidden />}
            title="Your exam date has passed"
            description="Set a new exam date to get a plan again."
            action={
              <Button asChild>
                <Link to="/app/account">Update your exam date</Link>
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={<Sparkles aria-hidden />}
            title="Choose a course to get a daily plan"
            description="Tell us what you are studying and when your exam is, and we will plan each day."
            action={
              <Button asChild>
                <Link to="/app/onboarding">Set up your course</Link>
              </Button>
            }
          />
        )}
      </Shell>
    )
  }
  return <Body plan={data} search={search} firstName={bootstrap.data?.first_name} />
}
