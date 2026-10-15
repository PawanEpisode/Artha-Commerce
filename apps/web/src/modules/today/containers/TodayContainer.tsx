import {
  addIsoDays,
  Alert,
  Button,
  CalendarClock,
  Container,
  EmptyState,
  Plus,
  Skeleton,
  Sparkles,
} from '@artha/design-system'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { useBootstrap } from '~/modules/personalization'

import { AddTaskSheet } from '../components/AddTaskSheet'
import { CelebrationCard } from '../components/CelebrationCard'
import { OverloadNotice } from '../components/OverloadNotice'
import { PaperTile } from '../components/PaperTile'
import { TaskRow } from '../components/TaskRow'
import { type SheetMode, TaskSheet } from '../components/TaskSheet'
import { TodayHeader } from '../components/TodayHeader'
import { TomorrowCard } from '../components/TomorrowCard'
import { WeekStrip } from '../components/WeekStrip'
import { useTaskActions } from '../hooks/useTaskActions'
import { useTodayFlag } from '../hooks/useTodayFlag'
import { useDayPreview, useTodayPlan, useTodaySettings } from '../hooks/useTodayQueries'
import { isFeatureDisabled, markCelebrated } from '../lib/api'
import { todayKeys } from '../lib/keys'
import { nextOpenTaskId } from '../lib/optimistic'
import { groupTasks, LONG_DAY_MINUTES, screenState, selectedTile, tileViews } from '../lib/plan'
import type { TodaySearch } from '../lib/search'
import { hourIn } from '../lib/time'
import { isEmptyPlan, type OpenResult, type Plan, type Task } from '../lib/types'

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

/** Moves keyboard focus to the next open row's tick (or the list heading) once the list has re-rendered. */
function focusSoon(id: string | null) {
  const run = () => {
    const el = (id && document.getElementById(`task-${id}-check`)) || document.getElementById('open-tasks')
    el?.focus()
  }
  requestAnimationFrame(() => requestAnimationFrame(run))
}

function Section({
  id,
  title,
  muted,
  children,
}: {
  id: string
  title: string
  muted?: boolean
  children: React.ReactNode
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2
        id={id}
        tabIndex={-1}
        className={`font-display text-lg font-bold outline-none ${muted ? 'text-muted-foreground' : ''}`}
      >
        {title}
      </h2>
      {children}
    </section>
  )
}

function Body({ plan, search, firstName }: { plan: Plan; search: TodaySearch; firstName?: string | null }) {
  const navigate = useNavigate({ from: '/app/today/' })
  const qc = useQueryClient()
  const actions = useTaskActions()
  const settings = useTodaySettings()
  const [sheet, setSheet] = useState<{ id: string; mode: SheetMode } | null>(
    search.task ? { id: search.task, mode: 'why' } : null,
  )
  const [burst, setBurst] = useState(false)
  const celebrating = useRef(false)

  const state = screenState(plan)
  const views = tileViews(plan)
  const chosen = selectedTile(views, search.paper)
  const groups = groupTasks(chosen ? chosen.tasks : plan.tasks)
  const choose = (key: string | undefined) =>
    void navigate({ search: (prev) => ({ ...prev, paper: key }), replace: true, resetScroll: false })

  // The celebration shows once per day on any device: show it now, then record it.
  useEffect(() => {
    if (!plan.celebrate || celebrating.current) return
    celebrating.current = true
    setBurst(true)
    void markCelebrated()
      .then(() =>
        qc.setQueryData<OpenResult>(todayKeys.plan, (old) =>
          old && old.state === 'ready' ? { ...old, celebrate: false } : old,
        ),
      )
      .catch(() => {
        celebrating.current = false // try again on the next refresh; the burst already played
      })
  }, [plan.celebrate, qc])

  const hour = hourIn(plan.server_time, plan.tz)
  const settled = plan.closing !== null
  const wantsTomorrow = settings.data?.show_tomorrow !== false && (settled || hour >= 18)
  const tomorrow = useDayPreview(wantsTomorrow ? addIsoDays(plan.date, 1) : null)

  const task = sheet ? (plan.tasks.find((t) => t.id === sheet.id) ?? null) : null
  const closeSheet = () => {
    setSheet(null)
    if (search.task) void navigate({ search: (prev) => ({ ...prev, task: undefined }), replace: true })
  }
  const withFocus = (t: { id: string }, run: () => unknown) => {
    const next = nextOpenTaskId(groups.open, t.id)
    void Promise.resolve(run()).then(() => focusSoon(next))
  }
  const onTick = (t: Task) =>
    t.manual_action ? setSheet({ id: t.id, mode: 'tick' }) : withFocus(t, () => actions.tick(t))
  const onUntick = (t: Task) => {
    const entry = actions.canUndo(t.id)
    if (entry) void actions.undo(t, entry.from, entry.back)
  }
  const onStart = async (t: Task) => {
    const link = await actions.start(t)
    if (link)
      void navigate({
        to: link.path as never,
        search: { ...link.search, from: 'today', task: t.id } as never,
      })
  }
  const row = (t: Task) => (
    <TaskRow
      key={t.id}
      task={t}
      highlighted={search.task === t.id}
      busy={actions.busy.has(t.id)}
      undoable={actions.canUndo(t.id)?.from === 'done'}
      onTick={onTick}
      onUntick={onUntick}
      onStart={(x) => void onStart(x)}
      onMenu={(x) => setSheet({ id: x.id, mode: 'menu' })}
    />
  )

  return (
    <Shell>
      <TodayHeader plan={plan} firstName={firstName} onStart={(t) => void onStart(t)} />
      {plan.partial ? (
        <Alert variant="info">
          Some suggestions are missing right now, so today's list may be shorter than usual. Reload in a moment to try
          again.
        </Alert>
      ) : null}
      <CelebrationCard plan={plan} burst={burst} />
      <OverloadNotice backlog={plan.backlog} />
      {plan.planned_minutes > LONG_DAY_MINUTES ? (
        <Alert variant="info">That is a long day. Consider moving one task to tomorrow.</Alert>
      ) : null}

      {state === 'nothing_due' ? (
        <EmptyState
          icon={<CalendarClock aria-hidden />}
          title="Nothing is due today"
          description="You are caught up. Add a task of your own, or pick something from your syllabus to get ahead."
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

          <Section id="open-tasks" title={groups.open.length ? 'To do' : 'Nothing left to do'}>
            <ul className="space-y-2">{groups.open.map(row)}</ul>
          </Section>
          {groups.done.length ? (
            <Section id="done-tasks" title="Done">
              <ul className="space-y-2">{groups.done.map(row)}</ul>
            </Section>
          ) : null}
          {groups.parked.length ? (
            <Section id="parked-tasks" title="Skipped and snoozed" muted>
              <ul className="space-y-2">{groups.parked.map(row)}</ul>
            </Section>
          ) : null}
        </>
      )}

      <Button
        variant="outline"
        onClick={() => void navigate({ search: (prev) => ({ ...prev, add: true }), replace: true, resetScroll: false })}
      >
        <Plus aria-hidden /> Add your own task
      </Button>

      {tomorrow.data ? <TomorrowCard preview={tomorrow.data} /> : null}
      {plan.week ? <WeekStrip days={plan.week} today={plan.date} /> : null}

      <TaskSheet
        task={task}
        mode={sheet?.mode ?? 'menu'}
        today={plan.date}
        actions={actions}
        onMode={(mode) => sheet && setSheet({ id: sheet.id, mode })}
        onClose={closeSheet}
      />
      <AddTaskSheet
        open={search.add === true}
        plan={plan}
        actions={actions}
        onClose={() =>
          void navigate({ search: (prev) => ({ ...prev, add: undefined }), replace: true, resetScroll: false })
        }
      />
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
