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
  toast,
} from '@artha/design-system'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { useBootstrap } from '~/modules/personalization'

import { AddTaskSheet } from '../components/AddTaskSheet'
import { CelebrationCard } from '../components/CelebrationCard'
import { DayExtras } from '../components/DayExtras'
import { ExamDateCard } from '../components/ExamDateCard'
import { FirstPlanReveal } from '../components/FirstPlanReveal'
import { OverloadNotice } from '../components/OverloadNotice'
import { PaperTile } from '../components/PaperTile'
import { DayRolloverBar, StatusBanner } from '../components/StatusBanner'
import { TaskRow } from '../components/TaskRow'
import { type SheetMode, TaskSheet } from '../components/TaskSheet'
import { TodayHeader } from '../components/TodayHeader'
import { TomorrowCard } from '../components/TomorrowCard'
import { WeekStrip } from '../components/WeekStrip'
import { useCachedPlan } from '../hooks/useCachedPlan'
import { useExamDate } from '../hooks/useExamDate'
import { useNow } from '../hooks/useNow'
import { useOnline } from '../hooks/useOnline'
import { useTaskActions } from '../hooks/useTaskActions'
import { useTodayFlag } from '../hooks/useTodayFlag'
import { useDayPreview, useTodayPlan, useTodaySettings } from '../hooks/useTodayQueries'
import { useTodaySync } from '../hooks/useTodaySync'
import { backlogBucket, minutesBucket, timeBucket, trackToday } from '../lib/analytics'
import { isFeatureDisabled, markCelebrated } from '../lib/api'
import { saveCachedPlan } from '../lib/cache'
import { todayKeys } from '../lib/keys'
import { isLite, networkHints } from '../lib/lite'
import { type Banner, bannerFor, cacheStatus, dayRolledOver } from '../lib/offline'
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

interface BodyProps {
  plan: Plan
  search: TodaySearch
  firstName?: string | null
  /** A plan of an earlier day: shown dimmed, every action off. */
  readOnly: boolean
  lite: boolean
  /** The connection, queue and rollover notices, rendered above the header. */
  status: React.ReactNode
}

function Body({ plan, search, firstName, readOnly, lite, status }: BodyProps) {
  const navigate = useNavigate({ from: '/app/today/' })
  const qc = useQueryClient()
  const actions = useTaskActions()
  const settings = useTodaySettings()
  const exam = useExamDate(plan, !readOnly)
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
    if (readOnly || !plan.celebrate || celebrating.current) return
    celebrating.current = true
    setBurst(settings.data?.celebrate !== false)
    trackToday('today_celebration_viewed', {
      reduced_motion: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
    })
    void markCelebrated()
      .then(() =>
        qc.setQueryData<OpenResult>(todayKeys.plan, (old) =>
          old && old.state === 'ready' ? { ...old, celebrate: false } : old,
        ),
      )
      .catch(() => {
        celebrating.current = false // try again on the next refresh; the burst already played
      })
  }, [plan.celebrate, qc, readOnly, settings.data?.celebrate])

  const hour = hourIn(plan.server_time, plan.tz)
  const settled = plan.closing !== null
  const wantsTomorrow = settings.data?.show_tomorrow !== false && (settled || hour >= 18)
  const tomorrow = useDayPreview(wantsTomorrow && !readOnly ? addIsoDays(plan.date, 1) : null)
  const tomorrowSeen = useRef(false)
  useEffect(() => {
    if (tomorrow.data && !tomorrowSeen.current) {
      tomorrowSeen.current = true
      trackToday('today_tomorrow_viewed', { task_count: tomorrow.data.count })
    }
  }, [tomorrow.data])
  const overloadSeen = useRef<string | null>(null)
  useEffect(() => {
    if (overloadSeen.current === plan.date || plan.backlog.length === 0) return
    overloadSeen.current = plan.date
    for (const item of plan.backlog)
      trackToday('today_overload_shown', { kind: item.kind, backlog_bucket: backlogBucket(item.count) })
  }, [plan.backlog, plan.date])

  const task = sheet ? (plan.tasks.find((t) => t.id === sheet.id) ?? null) : null
  const whyFor = sheet?.mode === 'why' ? (task?.id ?? null) : null
  useEffect(() => {
    if (whyFor && task) trackToday('today_why_opened', { kind: task.kind, reason_code: task.reason_code })
    // sent when the "Why this?" view opens for a task, not on every refetch of that task
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [whyFor])
  // The first-plan reveal (after onboarding) stays a few seconds, then the address is cleaned up.
  useEffect(() => {
    if (search.from !== 'onboarding') return
    const timer = window.setTimeout(
      () => void navigate({ search: (prev) => ({ ...prev, from: undefined }), replace: true, resetScroll: false }),
      6000,
    )
    return () => window.clearTimeout(timer)
  }, [search.from, navigate])
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
      readOnly={readOnly}
      busy={actions.busy.has(t.id)}
      undoable={actions.canUndo(t.id)?.from === 'done'}
      onKeep={(x) => void actions.edit(x, { keep: true }).then(() => toast.success('Kept on your list'))}
      onStuckSnooze={(x) => setSheet({ id: x.id, mode: 'snooze' })}
      onStuckDelete={(x) => void actions.remove(x)}
      onTick={onTick}
      onUntick={onUntick}
      onStart={(x) => void onStart(x)}
      onMenu={(x) => setSheet({ id: x.id, mode: 'menu' })}
    />
  )

  return (
    <Shell>
      {status}
      {search.from === 'onboarding' && !readOnly ? <FirstPlanReveal plan={plan} lite={lite} /> : null}
      <TodayHeader plan={plan} firstName={firstName} onStart={(t) => void onStart(t)} lite={lite} />
      {exam.offer && !readOnly ? (
        <ExamDateCard
          terms={exam.terms}
          today={plan.date}
          pending={exam.pending}
          error={exam.error}
          onPickTerm={exam.pickTerm}
          onCustomDate={exam.customDate}
          onDismiss={exam.dismiss}
        />
      ) : null}
      {plan.partial ? (
        <Alert variant="info">
          Some suggestions are missing right now, so today's list may be shorter than usual. Reload in a moment to try
          again.
        </Alert>
      ) : null}
      <CelebrationCard plan={plan} burst={burst} lite={lite} />
      <DayExtras plan={plan} readOnly={readOnly} />
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
                    lite={lite}
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

      {readOnly ? null : (
        <Button
          variant="outline"
          onClick={() =>
            void navigate({ search: (prev) => ({ ...prev, add: true }), replace: true, resetScroll: false })
          }
        >
          <Plus aria-hidden /> Add your own task
        </Button>
      )}

      {tomorrow.data ? <TomorrowCard preview={tomorrow.data} /> : null}
      {plan.week && !lite ? <WeekStrip days={plan.week} today={plan.date} /> : null}

      <TaskSheet
        task={readOnly ? null : task}
        mode={sheet?.mode ?? 'menu'}
        today={plan.date}
        actions={actions}
        onMode={(mode) => sheet && setSheet({ id: sheet.id, mode })}
        onClose={closeSheet}
      />
      <AddTaskSheet
        open={search.add === true && !readOnly}
        plan={plan}
        actions={actions}
        onClose={() =>
          void navigate({ search: (prev) => ({ ...prev, add: undefined }), replace: true, resetScroll: false })
        }
      />
    </Shell>
  )
}

function EmptyStates({ state }: { state: 'not_enrolled' | 'post_exam' }) {
  return (
    <Shell>
      {state === 'post_exam' ? (
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

const openSource = (from: TodaySearch['from']): string =>
  from === 'notification' || from === 'email'
    ? 'reminder'
    : from === 'workspace' || from === 'onboarding'
      ? 'redirect'
      : 'nav'

/**
 * /app/today (PRD 7.3). Gate on the flag, then show the best plan there is: the live one, else the one cached on this device (painted
 * at once, with "Updating", or with an offline, stale or earlier-day notice). Ticks and own tasks made offline queue and replay.
 */
export function TodayContainer({ search }: { search: TodaySearch }) {
  const enabled = useTodayFlag()
  const bootstrap = useBootstrap()
  const online = useOnline()
  const now = useNow()
  const cache = useCachedPlan(enabled)
  const plan = useTodayPlan(enabled)
  const settings = useTodaySettings(enabled)
  const sync = useTodaySync(enabled)
  const qc = useQueryClient()
  const mounted = useRef(typeof performance === 'undefined' ? 0 : performance.now())
  const opened = useRef(false)

  const live = plan.data && !isEmptyPlan(plan.data) ? plan.data : null
  const cached = cache.entry?.plan ?? null
  const shown: Plan | null = live ?? cached
  const lite = isLite(settings.data?.lite_mode, networkHints())

  // Keep the device copy current (ticks and own tasks made offline included), so a reload without a network still has the list.
  useEffect(() => {
    if (cache.userId && live) void saveCachedPlan(cache.userId, live)
  }, [cache.userId, live])

  // Where the plan on screen came from decides the notice: a cached plan, or a live one that is now offline or failing to refresh.
  const failing = plan.isError && !isFeatureDisabled(plan.error)
  const savedAt = live ? plan.dataUpdatedAt : (cache.entry?.savedAt ?? 0)
  const fromCache = !live && cached !== null
  const cacheInfo =
    shown && (fromCache || !online || failing)
      ? { status: cacheStatus({ savedAt, planDate: shown.date, tz: shown.tz }, now), savedAt }
      : null
  const banner: Banner = bannerFor({
    online,
    waiting: sync.waiting,
    cache: cacheInfo,
    refreshing: plan.isFetching,
    now,
  })
  const readOnly = banner.kind === 'previous_day'
  const rolled = Boolean(live) && online && dayRolledOver(live?.date ?? '', live?.tz ?? 'UTC', now)
  const refresh = () => void qc.invalidateQueries({ queryKey: todayKeys.plan })

  // `today_opened` once, the first time something is on screen.
  const ready = plan.data !== undefined || shown !== null
  useEffect(() => {
    if (!ready || opened.current) return
    opened.current = true
    const data = plan.data
    const empty = data && isEmptyPlan(data)
    trackToday('today_opened', {
      source: openSource(search.from),
      plan_state: empty ? data.state : live ? 'fresh' : 'cached',
      task_count: shown?.counts.planned ?? 0,
      planned_minutes_bucket: minutesBucket(shown?.planned_minutes ?? 0),
      from_cache: !live && shown !== null,
      render_time_bucket: timeBucket((typeof performance === 'undefined' ? 0 : performance.now()) - mounted.current),
      lite,
    })
  }, [ready, plan.data, live, shown, search.from, lite])

  if (!enabled || isFeatureDisabled(plan.error)) return <Unavailable />
  if (plan.data && isEmptyPlan(plan.data)) return <EmptyStates state={plan.data.state} />

  if (!shown) {
    if (!online && cache.loaded)
      return (
        <Shell>
          <Alert variant="info">
            <p>
              You are offline and there is no saved plan on this device yet. Connect to the internet to get today's
              plan.
            </p>
          </Alert>
        </Shell>
      )
    if (plan.isError)
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
    return <Loading />
  }

  const status = (
    <>
      <StatusBanner banner={banner} planDate={shown.date} onRefresh={refresh} />
      {failing && online && fromCache ? (
        <Alert variant="info">We could not refresh just now, so this is your last saved plan.</Alert>
      ) : null}
      {rolled ? <DayRolloverBar onShow={refresh} /> : null}
    </>
  )
  return (
    <Body
      plan={shown}
      search={search}
      firstName={bootstrap.data?.first_name}
      readOnly={readOnly}
      lite={lite}
      status={status}
    />
  )
}
