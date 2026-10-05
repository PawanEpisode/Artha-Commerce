import { Alert, Button, Plus, Skeleton } from '@artha/design-system'
import { useEffect, useRef, useState } from 'react'

import { track } from '~/modules/observability'

import { GoalRings } from '../components/GoalRings'
import { StopwatchCard } from '../components/StopwatchCard'
import { WeeklySummaryCard } from '../components/WeeklySummaryCard'
import { useStopwatch } from '../hooks/useStopwatch'
import { useChapterOptions, useSubjectOptions } from '../hooks/useTagOptions'
import { useGoals, useSessionsPage, useToday, useTrackerSettings, useWeeklySummary } from '../hooks/useTrackerQueries'
import { formatDuration } from '../lib/duration'
import type { ActivityType } from '../lib/types'
import { SessionFormDialog } from './SessionFormDialog'
import { SessionsPanel } from './SessionsPanel'
import { TrackerShell } from './TrackerShell'

function Today({ tz }: { tz: string }) {
  const settings = useTrackerSettings().data
  const today = useToday()
  const timer = useStopwatch()
  const sw = timer.stopwatch
  const subjects = useSubjectOptions()
  const [pick, setPick] = useState<{
    subject_id: string | null
    chapter_id: string | null
    activity_type: ActivityType
  }>({ subject_id: null, chapter_id: null, activity_type: settings?.default_activity_type ?? 'other' })
  const shown = sw ? { subject_id: sw.subject_id, chapter_id: sw.chapter_id, activity_type: sw.activity_type } : pick
  const chapters = useChapterOptions(shown.subject_id)
  const [adding, setAdding] = useState(false)
  const goals = useGoals()
  const weekly = useWeeklySummary()
  const sessions = useSessionsPage({ from: today, to: today, include_notes: true })
  const todays = sessions.data?.pages.flatMap((p) => p.results) ?? []
  const total = todays.reduce((sum, s) => sum + s.focus_seconds, 0)

  // Ask "still studying?" once per idle spell; the server auto-pauses if the answer does not come.
  const { idle } = timer
  useEffect(() => {
    if (sw?.idle_due && !sw.idle_pending && !idle.isPending) idle.mutate('prompted')
  }, [sw?.idle_due, sw?.idle_pending, idle])

  const reached = useRef(false)
  const percent = goals.data?.progress.daily.percent ?? 0
  useEffect(() => {
    if (percent >= 100 && !reached.current) {
      reached.current = true
      track('goal_reached', { period: 'daily' })
    }
  }, [percent])

  const sentWeekly = useRef(false)
  useEffect(() => {
    if (weekly.data && !sentWeekly.current) {
      sentWeekly.current = true
      track('weekly_summary_viewed')
    }
  }, [weekly.data])

  const onPick = (patch: Partial<typeof pick>) => {
    if (sw) timer.context.mutate(patch)
    else setPick((p) => ({ ...p, ...patch }))
  }

  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Time tracker</h1>
        <p className="text-muted-foreground">Study time today: {formatDuration(total)}</p>
      </header>

      <StopwatchCard
        stopwatch={sw}
        seconds={timer.seconds}
        busy={timer.busy}
        otherLive={timer.state?.live ?? null}
        subjects={subjects}
        chapters={chapters}
        value={shown}
        onValueChange={onPick}
        onStart={() => timer.start.mutate(pick)}
        onPause={() => timer.toggle.mutate('pause')}
        onResume={() => timer.toggle.mutate('resume')}
        onStop={() => timer.stop.mutate(true)}
        onDiscard={() => timer.stop.mutate(false)}
        idlePending={!!sw?.idle_pending}
        onStillStudying={() => idle.mutate('still_studying')}
      />

      {goals.data ? (
        <GoalRings progress={goals.data.progress} />
      ) : goals.isError ? null : (
        <Skeleton className="h-48 w-full" />
      )}

      <section aria-labelledby="today-heading" className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 id="today-heading" className="text-lg font-bold">
            Today
          </h2>
          <Button variant="outline" onClick={() => setAdding(true)}>
            <Plus aria-hidden /> Add time
          </Button>
        </div>
        {sessions.isError ? (
          <Alert variant="error">
            <span role="alert">We could not load today's sessions.</span>
          </Alert>
        ) : (
          <SessionsPanel
            sessions={todays}
            tz={tz}
            defaultActivity={settings?.default_activity_type ?? 'other'}
            emptyText="No study time yet today."
          />
        )}
      </section>

      {weekly.data && weekly.data.total_seconds > 0 ? <WeeklySummaryCard data={weekly.data} /> : null}

      <SessionFormDialog
        open={adding}
        onOpenChange={setAdding}
        tz={tz}
        defaultActivity={settings?.default_activity_type ?? 'other'}
      />
    </>
  )
}

export function TrackerContainer() {
  return <TrackerShell>{(tz) => <Today tz={tz} />}</TrackerShell>
}
