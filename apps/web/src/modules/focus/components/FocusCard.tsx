import { Alert, Button, Card, CardContent, Coffee, Kbd, Pause, Play, SkipForward, Square } from '@artha/design-system'

import { ContextPicker, type PickerValue } from '~/modules/tracker'

import { MAX_EXTENSIONS, type PresetKey, type Timings } from '../lib/presets'
import { PHASE_LABEL, startLabel } from '../lib/timer-math'
import type { FocusTimer, IdleInfo } from '../lib/types'
import { CycleDots } from './CycleDots'
import { PresetPicker } from './PresetPicker'
import { TimerRing } from './TimerRing'

interface Props {
  timer: FocusTimer | null
  idle: IdleInfo | null
  remainingSeconds: number
  percent: number
  busy: boolean
  /** The other kind of live timer that blocks Start ("stopwatch"), if any. */
  otherLive: string | null
  timings: Timings
  onTimingsChange: (timings: Timings, preset: PresetKey) => void
  subjects: Array<{ id: string; name: string }>
  chapters: Array<{ id: string; name: string }>
  value: PickerValue
  onValueChange: (patch: Partial<PickerValue>) => void
  onStart: () => void
  onStartFocusInsteadOfBreak: () => void
  onPause: () => void
  onResume: () => void
  onExtend: () => void
  onSkipBreak: () => void
  onEndEarly: () => void
  error?: string | null
  /** Polite live-region text for screen readers ("Focus round done. Time for a short break."). */
  announcement: string
}

/** The Pomodoro timer: ring, round dots, controls and, while nothing runs, the preset and context pickers. */
export function FocusCard(p: Props) {
  const t = p.timer
  const running = t?.status === 'running'
  const onBreak = t && t.phase !== 'focus'
  const dueBreak = !t && p.idle && p.idle.next_phase !== 'focus'
  const caption = t
    ? t.phase === 'focus'
      ? `Round ${t.round_number} of ${t.rounds_before_long}`
      : `After round ${t.round_number}`
    : dueBreak
      ? 'A break is due'
      : p.idle && p.idle.next_round > 1
        ? `Round ${p.idle.next_round} of ${p.idle.rounds_before_long} is next`
        : 'Pick a rhythm and start'
  const extensionsLeft = t ? MAX_EXTENSIONS - t.extension_count : 0

  return (
    <Card>
      <CardContent className="space-y-6 p-6">
        <TimerRing
          phase={t?.phase ?? null}
          status={t?.status ?? null}
          remainingSeconds={t ? p.remainingSeconds : p.timings.focus_minutes * 60}
          percent={t ? p.percent : 0}
          caption={caption}
        />
        <CycleDots
          total={t?.rounds_before_long ?? p.idle?.rounds_before_long ?? p.timings.rounds_before_long}
          current={t ? (t.phase === 'focus' ? t.round_number : t.round_number + 1) : (p.idle?.next_round ?? 1)}
          active={t?.phase === 'focus'}
        />

        <p role="status" aria-live="polite" className="sr-only">
          {p.announcement}
        </p>
        {p.otherLive && !t ? (
          <Alert variant="info">
            <span role="status">The {p.otherLive} is running. Stop it before you start a focus round.</span>
          </Alert>
        ) : null}
        {p.error ? (
          <Alert variant="error">
            <span role="alert">{p.error}</span>
          </Alert>
        ) : null}

        {!t ? (
          <div className="space-y-4">
            <PresetPicker value={p.timings} onChange={p.onTimingsChange} disabled={p.busy} />
            <ContextPicker
              subjects={p.subjects}
              chapters={p.chapters}
              value={p.value}
              onChange={p.onValueChange}
              disabled={p.busy}
            />
          </div>
        ) : (
          <ContextPicker
            subjects={p.subjects}
            chapters={p.chapters}
            value={p.value}
            onChange={p.onValueChange}
            disabled={p.busy || t.status === 'away'}
          />
        )}

        <div className="flex flex-wrap justify-center gap-3">
          {!t ? (
            <>
              <Button size="lg" onClick={p.onStart} disabled={p.busy || !!p.otherLive}>
                {dueBreak ? <Coffee aria-hidden /> : <Play aria-hidden />} {startLabel(p.idle)}
              </Button>
              {dueBreak ? (
                <Button
                  size="lg"
                  variant="ghost"
                  onClick={p.onStartFocusInsteadOfBreak}
                  disabled={p.busy || !!p.otherLive}
                >
                  Skip the break
                </Button>
              ) : null}
            </>
          ) : t.status === 'away' ? null : onBreak ? (
            <Button size="lg" variant="outline" onClick={p.onSkipBreak} disabled={p.busy}>
              <SkipForward aria-hidden /> Skip break
            </Button>
          ) : (
            <>
              {running ? (
                <Button size="lg" variant="outline" onClick={p.onPause} disabled={p.busy}>
                  <Pause aria-hidden /> Pause
                </Button>
              ) : (
                <Button size="lg" onClick={p.onResume} disabled={p.busy}>
                  <Play aria-hidden /> Resume
                </Button>
              )}
              <Button size="lg" variant="outline" onClick={p.onExtend} disabled={p.busy || !t.can_extend}>
                +5 min{extensionsLeft > 0 ? ` (${extensionsLeft} left)` : ''}
              </Button>
              <Button size="lg" variant="ghost" onClick={p.onEndEarly} disabled={p.busy}>
                <Square aria-hidden /> End early
              </Button>
            </>
          )}
        </div>
        <p className="text-center text-xs text-muted-foreground">
          {t
            ? `${PHASE_LABEL[t.phase]} runs on our clock, so a reload or another device shows the same time. `
            : 'Rounds under one minute are not saved. '}
          <Kbd>Space</Kbd> {t ? 'pauses' : 'starts'}
          {onBreak ? (
            <>
              , <Kbd>S</Kbd> skips
            </>
          ) : t ? (
            <>
              , <Kbd>E</Kbd> ends early
            </>
          ) : null}
          .
        </p>
      </CardContent>
    </Card>
  )
}
