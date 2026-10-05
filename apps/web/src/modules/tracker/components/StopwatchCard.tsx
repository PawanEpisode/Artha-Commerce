import { Alert, Button, Card, CardContent, Pause, Play, Square, Timer } from '@artha/design-system'

import { formatClock, spokenDuration } from '../lib/duration'
import type { Stopwatch } from '../lib/types'
import { ContextPicker, type PickerValue } from './ContextPicker'

interface Props {
  stopwatch: Stopwatch | null
  seconds: number
  busy: boolean
  /** Name of another live timer that blocks starting this one ("pomodoro"), if any. */
  otherLive: string | null
  subjects: Array<{ id: string; name: string }>
  chapters: Array<{ id: string; name: string }>
  value: PickerValue
  onValueChange: (patch: Partial<PickerValue>) => void
  onStart: () => void
  onPause: () => void
  onResume: () => void
  onStop: () => void
  onDiscard: () => void
  /** Idle check: the server asked whether the student is still studying. */
  idlePending: boolean
  onStillStudying: () => void
  error?: string | null
}

/** The stopwatch: a big clock, the context pickers and the four controls. The clock is derived from timestamps. */
export function StopwatchCard(props: Props) {
  const { stopwatch: sw, seconds, busy, otherLive } = props
  const running = sw?.status === 'running'
  return (
    <Card>
      <CardContent className="space-y-5 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-lg font-bold">
            <Timer className="size-5 text-primary" aria-hidden /> Stopwatch
          </h2>
          {sw ? (
            <span className="text-sm font-medium text-muted-foreground">{running ? 'Running' : 'Paused'}</span>
          ) : null}
        </div>

        <p
          role="timer"
          aria-label={`Elapsed ${spokenDuration(seconds)}`}
          className="text-center font-display text-5xl font-extrabold tracking-tight tabular-nums sm:text-6xl"
        >
          <span aria-hidden>{formatClock(seconds)}</span>
        </p>

        {props.idlePending ? (
          <Alert variant="info">
            <span role="alert" className="flex flex-wrap items-center gap-3">
              Still studying? The timer pauses on its own if you do not answer.
              <Button size="sm" onClick={props.onStillStudying}>
                Yes, still studying
              </Button>
            </span>
          </Alert>
        ) : null}

        {otherLive && !sw ? (
          <Alert variant="info">
            <span role="status">A {otherLive} timer is running. Stop it before you start the stopwatch.</span>
          </Alert>
        ) : null}
        {props.error ? (
          <Alert variant="error">
            <span role="alert">{props.error}</span>
          </Alert>
        ) : null}

        <ContextPicker
          subjects={props.subjects}
          chapters={props.chapters}
          value={props.value}
          onChange={props.onValueChange}
          disabled={busy}
        />

        <div className="flex flex-wrap justify-center gap-3">
          {!sw ? (
            <Button size="lg" onClick={props.onStart} disabled={busy || !!otherLive}>
              <Play aria-hidden /> Start
            </Button>
          ) : (
            <>
              {running ? (
                <Button size="lg" variant="outline" onClick={props.onPause} disabled={busy}>
                  <Pause aria-hidden /> Pause
                </Button>
              ) : (
                <Button size="lg" onClick={props.onResume} disabled={busy}>
                  <Play aria-hidden /> Resume
                </Button>
              )}
              <Button size="lg" onClick={props.onStop} disabled={busy}>
                <Square aria-hidden /> Stop and save
              </Button>
              <Button size="lg" variant="ghost" onClick={props.onDiscard} disabled={busy}>
                Discard
              </Button>
            </>
          )}
        </div>
        <p className="text-center text-xs text-muted-foreground">
          Time under one minute is not saved. The clock keeps running if you close this tab.
        </p>
      </CardContent>
    </Card>
  )
}
