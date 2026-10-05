import { formatDuration } from '@artha/design-system'

import { fromLocalInput } from './duration'
import { CLOCK_SKEW_SECONDS, MAX_MANUAL_SPAN_SECONDS, MIN_SESSION_SECONDS, NOTE_MAX_CHARS } from './limits'
import type { ActivityType, ManualInput, SessionEdit, StudySession } from './types'

export type EntryMode = 'range' | 'duration'

export interface SessionFormValues {
  mode: EntryMode
  /** "datetime-local" values, read in the tracker time zone. */
  start: string
  end: string
  /** Whole minutes typed in the hours + minutes field; null while it is empty. */
  durationMinutes: number | null
  subject_id: string | null
  chapter_id: string | null
  activity_type: ActivityType
  note: string
  onOverlap: 'trim' | 'keep' | 'reject' | null
  confirmOld: boolean
}

const MAX_SPAN_MESSAGE = `A single entry can be at most ${formatDuration(MAX_MANUAL_SPAN_SECONDS / 60, 'long')}.`

export type FormErrors = Partial<Record<'start' | 'end' | 'duration' | 'note', string>>

/** Checks a form before it is sent. The server checks again; this only saves a round trip for the common slips. */
export function validateForm(v: SessionFormValues, tz: string, nowMs: number): FormErrors {
  const errors: FormErrors = {}
  if (!v.start) {
    errors.start = 'Choose when you started.'
    return errors
  }
  const start = fromLocalInput(v.start, tz).getTime()
  let end: number
  if (v.mode === 'duration') {
    const seconds = Math.round((v.durationMinutes ?? 0) * 60)
    if (!(seconds >= MIN_SESSION_SECONDS)) errors.duration = 'Enter at least 1 minute.'
    else if (seconds > MAX_MANUAL_SPAN_SECONDS) errors.duration = MAX_SPAN_MESSAGE
    end = start + seconds * 1000
  } else {
    if (!v.end) {
      errors.end = 'Choose when you finished.'
      return errors
    }
    end = fromLocalInput(v.end, tz).getTime()
    if (end <= start) errors.end = 'The end must be after the start.'
    else if ((end - start) / 1000 < MIN_SESSION_SECONDS) errors.end = 'Enter at least 1 minute.'
    else if ((end - start) / 1000 > MAX_MANUAL_SPAN_SECONDS) errors.end = MAX_SPAN_MESSAGE
  }
  if (!errors.end && end > nowMs + CLOCK_SKEW_SECONDS * 1000) errors.end = 'Study time cannot be in the future.'
  if (v.note.length > NOTE_MAX_CHARS) errors.note = `Keep the note to ${NOTE_MAX_CHARS} characters.`
  return errors
}

export function toManualInput(v: SessionFormValues, tz: string, clientId: string): ManualInput {
  const started = fromLocalInput(v.start, tz)
  const base: ManualInput = {
    client_id: clientId,
    started_at: started.toISOString(),
    subject_id: v.subject_id,
    chapter_id: v.chapter_id,
    activity_type: v.activity_type,
    note: v.note.trim(),
    on_overlap: v.onOverlap,
    confirm_old: v.confirmOld,
  }
  return v.mode === 'duration'
    ? { ...base, duration_seconds: Math.round((v.durationMinutes ?? 0) * 60) }
    : { ...base, ended_at: fromLocalInput(v.end, tz).toISOString() }
}

/** Only what changed, so an edit of the note does not rewrite the times (and the audit trail stays honest). */
export function toEdit(v: SessionFormValues, tz: string, original: StudySession): SessionEdit {
  const patch: SessionEdit = {}
  if (v.subject_id !== original.subject_id) patch.subject_id = v.subject_id
  if (v.chapter_id !== original.chapter_id) patch.chapter_id = v.chapter_id
  if (v.activity_type !== original.activity_type) patch.activity_type = v.activity_type
  if (v.note.trim() !== (original.note ?? '')) patch.note = v.note.trim()
  const started = fromLocalInput(v.start, tz).toISOString()
  const ended = fromLocalInput(v.end, tz).toISOString()
  if (Date.parse(started) !== Date.parse(original.started_at)) patch.started_at = started
  if (Date.parse(ended) !== Date.parse(original.ended_at)) patch.ended_at = ended
  if (v.confirmOld && (patch.started_at || patch.ended_at)) patch.confirm_old = true
  return patch
}
