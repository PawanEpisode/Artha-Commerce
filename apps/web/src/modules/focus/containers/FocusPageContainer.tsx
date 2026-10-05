import { Button } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { track } from '~/modules/observability'
import {
  type ActivityType,
  hasSubjectAndChapter,
  nowMs,
  type PickerValue,
  useChapterOptions,
  useGoals,
  useSubjectOptions,
  useToday,
  useTrackerSettings,
} from '~/modules/tracker'

import { AwayDialog } from '../components/AwayDialog'
import { ConflictDialog } from '../components/ConflictDialog'
import { EndEarlyDialog } from '../components/EndEarlyDialog'
import { FirstRunIntro } from '../components/FirstRunIntro'
import { FocusCard } from '../components/FocusCard'
import { TodayCard } from '../components/TodayCard'
import { useTimerTitle } from '../hooks/useDocumentTitle'
import { useRoundsOn } from '../hooks/useFocusQueries'
import { useSaveFocusSettings } from '../hooks/useFocusSettings'
import { type FocusTimerApi, useFocusTimer } from '../hooks/useFocusTimer'
import { errorCode } from '../lib/api'
import { unlockAudio } from '../lib/chime'
import { matchPreset, type PresetKey, presetTimings, type Timings } from '../lib/presets'
import { shortcutFor } from '../lib/shortcuts'
import { elapsedSeconds, percentDone } from '../lib/timer-math'
import { FocusShell } from './FocusShell'

export interface FocusSearch {
  subject?: string
  chapter?: string
  preset?: 'classic' | 'deep' | 'light'
  activity?: ActivityType
}

const DEFAULT_TIMINGS: Timings = presetTimings('classic')

function Body({ search, f }: { search: FocusSearch; f: FocusTimerApi }) {
  const save = useSaveFocusSettings()
  const trackerSettings = useTrackerSettings().data
  const subjects = useSubjectOptions()
  const today = useToday()
  const goals = useGoals().data?.progress
  const rounds = useRoundsOn(today).data ?? 0
  const t = f.timer
  const settings = f.settings

  const [timings, setTimings] = useState<{ timings: Timings; preset: PresetKey }>({
    timings: DEFAULT_TIMINGS,
    preset: 'classic',
  })
  const [pick, setPick] = useState<PickerValue>({
    subject_id: null,
    chapter_id: null,
    activity_type: search.activity ?? 'other',
  })
  const [ending, setEnding] = useState(false)
  const [conflictOpen, setConflictOpen] = useState(false)

  // Take the student's saved rhythm once it is known (and the URL's preset, if the link carries one).
  const seeded = useRef(false)
  useEffect(() => {
    if (!settings || seeded.current) return
    seeded.current = true
    const fromSettings: Timings = {
      focus_minutes: settings.focus_minutes,
      short_break_minutes: settings.short_break_minutes,
      long_break_minutes: settings.long_break_minutes,
      rounds_before_long: settings.rounds_before_long,
    }
    const next = search.preset ? presetTimings(search.preset) : fromSettings
    setTimings({ timings: next, preset: search.preset ?? settings.preset ?? matchPreset(next) })
  }, [settings, search.preset])

  useEffect(() => {
    if (trackerSettings && !search.activity)
      setPick((p) => (p.activity_type === 'other' ? { ...p, activity_type: trackerSettings.default_activity_type } : p))
  }, [trackerSettings, search.activity])

  // ?subject= and ?chapter= take a key or an id.
  const linkedSubject = useRef(false)
  useEffect(() => {
    if (linkedSubject.current || !search.subject || subjects.length === 0) return
    linkedSubject.current = true
    const s = subjects.find((x) => x.id === search.subject || x.key === search.subject)
    if (s) setPick((p) => ({ ...p, subject_id: s.id }))
  }, [search.subject, subjects])
  const chapterOptions = useChapterOptions(t ? t.subject_id : pick.subject_id)
  const linkedChapter = useRef(false)
  useEffect(() => {
    if (linkedChapter.current || !search.chapter || chapterOptions.length === 0 || !pick.subject_id) return
    linkedChapter.current = true
    const c = chapterOptions.find((x) => x.id === search.chapter || x.key === search.chapter)
    if (c) setPick((p) => ({ ...p, chapter_id: c.id }))
  }, [search.chapter, chapterOptions, pick.subject_id])

  const shown: PickerValue = t
    ? { subject_id: t.subject_id, chapter_id: t.chapter_id, activity_type: t.activity_type }
    : pick
  const onPick = (patch: Partial<PickerValue>) => {
    if (t) f.context.mutate(patch)
    else setPick((p) => ({ ...p, ...patch }))
  }

  const doStart = (phase: 'focus' | 'short_break' | 'long_break' = 'focus') => {
    if (!hasSubjectAndChapter(pick)) return
    unlockAudio()
    const body = timings.preset === 'custom' ? { preset: 'custom', ...timings.timings } : { preset: timings.preset }
    f.start(
      { ...(phase === 'focus' ? body : {}), phase, ...pick },
      { has_subject: !!pick.subject_id, resumed_cycle: (f.idle?.next_round ?? 1) > 1 },
    )
  }
  const startFocusInsteadOfBreak = () => doStart('focus')
  const primaryStart = () => doStart(f.idle && f.idle.next_phase !== 'focus' ? f.idle.next_phase : 'focus')

  // Conflicts (another timer already runs) open a dialog; the loaded state is already adopted by the hook.
  const liveKind =
    f.error && errorCode(f.error) === 'timer_already_active'
      ? f.live === 'stopwatch'
        ? 'stopwatch'
        : 'pomodoro'
      : null
  useEffect(() => {
    if (liveKind) setConflictOpen(true)
  }, [liveKind])

  // Goal reached: fire once when finished rounds push the shared daily goal over 100%.
  const percent = goals?.daily.percent ?? 0
  const lastPercent = useRef<number | null>(null)
  useEffect(() => {
    if (lastPercent.current !== null && lastPercent.current < 100 && percent >= 100) track('focus_goal_reached', {})
    lastPercent.current = percent
  }, [percent])

  useTimerTitle(t, 'Focus timer', f.remaining)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const action = shortcutFor(e, { dialogOpen: ending || conflictOpen || t?.status === 'away' })
      if (!action) return
      if (action === 'toggle') {
        e.preventDefault()
        if (f.busy) return
        if (!t) primaryStart()
        else if (t.phase === 'focus') (t.status === 'running' ? f.pause : f.resume)()
      } else if (action === 'skip' && t && t.phase !== 'focus' && !f.busy) f.skipBreak()
      else if (action === 'end' && t?.phase === 'focus' && t.status !== 'away') setEnding(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const studied = t ? elapsedSeconds(t, nowMs()) : 0
  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Focus timer</h1>
        <p className="text-muted-foreground">Study in focused rounds, then rest.</p>
      </header>

      {settings && !settings.intro_seen ? <FirstRunIntro onDismiss={() => save.mutate({ intro_seen: true })} /> : null}

      <FocusCard
        timer={t}
        idle={f.idle}
        remainingSeconds={f.remaining}
        percent={t ? percentDone(t, nowMs()) : 0}
        busy={f.busy}
        otherLive={f.live === 'stopwatch' ? 'stopwatch' : null}
        timings={timings.timings}
        preset={timings.preset}
        onTimingsChange={(next, preset) => setTimings({ timings: next, preset })}
        subjects={subjects}
        chapters={chapterOptions}
        value={shown}
        onValueChange={onPick}
        onStart={primaryStart}
        onStartFocusInsteadOfBreak={startFocusInsteadOfBreak}
        onPause={f.pause}
        onResume={f.resume}
        onExtend={f.extend}
        onSkipBreak={f.skipBreak}
        onEndEarly={() => setEnding(true)}
        announcement={f.announcement}
      />

      <TodayCard
        doneSeconds={goals?.daily.done_seconds ?? 0}
        targetMinutes={goals?.daily.target_minutes ?? 120}
        percent={percent}
        streak={goals?.streak ?? 0}
        rounds={rounds}
      />

      <EndEarlyDialog
        open={ending && !!t}
        studiedSeconds={studied}
        busy={f.busy}
        onClose={() => setEnding(false)}
        onEnd={(saveIt, reason) => {
          f.end(saveIt, reason)
          setEnding(false)
        }}
      />
      <AwayDialog
        open={t?.status === 'away'}
        plannedSeconds={t?.planned_seconds ?? 0}
        busy={f.claim.isPending}
        onAnswer={(count) => f.claim.mutate(count)}
      />
      <ConflictDialog
        open={conflictOpen}
        kind={liveKind ?? (f.live === 'stopwatch' ? 'stopwatch' : 'pomodoro')}
        onClose={() => {
          setConflictOpen(false)
          f.clearError()
        }}
        action={
          f.live === 'stopwatch' ? (
            <Button asChild>
              <Link to="/app/tracker">Open the stopwatch</Link>
            </Button>
          ) : undefined
        }
      />
    </>
  )
}

export function FocusPageContainer({ search }: { search: FocusSearch }) {
  const f = useFocusTimer()
  return (
    <FocusShell
      state={f.query.isPending ? 'loading' : f.query.isError && !f.featureDisabled ? 'error' : 'ready'}
      disabled={f.featureDisabled}
      onRetry={() => void f.query.refetch()}
    >
      <Body search={search} f={f} />
    </FocusShell>
  )
}
