import { Button, CircleCheck, Label, LoaderCircle, SelectField, TextField } from '@artha/design-system'
import { type FormEvent, useEffect, useState } from 'react'

import {
  ACTIVITIES,
  type Activity,
  ACTIVITY_EVENT,
  type ActivityProgress,
  EVENT_ACTIVITY,
  everythingLogged,
  logBlockedReason,
} from '../lib/rules'
import type { EventType } from '../lib/types'

interface Props {
  /** Clamped progress per activity (`chapterActivities`). An activity at its target cannot be chosen. */
  activities: Record<Activity, ActivityProgress>
  pending?: boolean
  onLog: (type: EventType, value: number | null) => void
}

const OPTIONS: Array<{ activity: Activity; label: string; scored: boolean }> = [
  { activity: 'practice', label: 'Practice set', scored: true },
  { activity: 'mocks', label: 'Mock test or past paper', scored: true },
  { activity: 'revisions', label: 'Revision', scored: false },
]

/**
 * Log a practice set, mock or revision (FR-15). Score is optional and a percent. An activity whose target is reached
 * is disabled with the reason beside the field; when all are reached the form gives way to a done state.
 */
export function LogActions({ activities, pending, onLog }: Props) {
  const firstOpen = OPTIONS.find((o) => activities[o.activity].canLog)?.activity ?? 'practice'
  const [activity, setActivity] = useState<Activity>(firstOpen)
  const [score, setScore] = useState('')

  // After a log fills an activity, move the selection to one that is still open.
  useEffect(() => {
    if (!activities[activity].canLog) setActivity(firstOpen)
  }, [activities, activity, firstOpen])

  if (everythingLogged(activities)) {
    return (
      <div role="status" className="flex items-start gap-3">
        <CircleCheck aria-hidden className="mt-0.5 size-6 shrink-0 text-success-fg" />
        <div>
          <p className="font-semibold">Everything planned for this chapter is logged.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Practice, mock tests and revision are all at target. Open another chapter to keep going.
          </p>
        </div>
      </div>
    )
  }

  const scored = OPTIONS.find((o) => o.activity === activity)?.scored ?? false
  const parsed = score.trim() === '' ? null : Number(score)
  const invalid = scored && parsed !== null && (!Number.isFinite(parsed) || parsed < 0 || parsed > 100)
  const blocked = ACTIVITIES.flatMap((a) => {
    const reason = logBlockedReason(a, activities[a])
    return reason ? [reason] : []
  })
  const canSubmit = activities[activity].canLog && !pending && !invalid

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    onLog(ACTIVITY_EVENT[activity], scored ? parsed : null)
    setScore('')
  }

  return (
    <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-[1fr_9rem_auto] sm:items-end">
      <div className="grid gap-2">
        <Label htmlFor="log-type">What did you finish?</Label>
        <SelectField
          id="log-type"
          value={ACTIVITY_EVENT[activity]}
          onValueChange={(next) => setActivity(EVENT_ACTIVITY[next as EventType])}
          options={OPTIONS.map(({ activity: a, label }) => ({
            value: ACTIVITY_EVENT[a],
            label: activities[a].canLog ? label : `${label} (all logged)`,
            disabled: !activities[a].canLog,
          }))}
        />
      </div>
      {scored ? (
        <TextField
          label="Score (optional)"
          inputMode="decimal"
          placeholder="0 to 100"
          value={score}
          onChange={(e) => setScore(e.target.value)}
          error={invalid ? 'Enter a score from 0 to 100.' : undefined}
        />
      ) : (
        <span aria-hidden className="hidden sm:block" />
      )}
      <Button type="submit" disabled={!canSubmit}>
        {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
        Log it
      </Button>
      {blocked.length > 0 ? (
        <ul className="space-y-1 text-sm text-muted-foreground sm:col-span-3">
          {blocked.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </form>
  )
}
