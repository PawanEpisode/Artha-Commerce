import { Checkbox, DurationField, Label, SegmentedControl, Textarea, TextField } from '@artha/design-system'
import { useId } from 'react'

import { friendlyDateTime } from '../lib/format'
import { MAX_MANUAL_SPAN_SECONDS, NOTE_MAX_CHARS } from '../lib/limits'
import type { EntryMode, FormErrors, SessionFormValues } from '../lib/sessionForm'
import { ContextPicker } from './ContextPicker'

interface Props {
  values: SessionFormValues
  onChange: (patch: Partial<SessionFormValues>) => void
  errors: FormErrors
  subjects: Array<{ id: string; name: string }>
  chapters: Array<{ id: string; name: string }>
  subjectsLoading?: boolean
  chaptersLoading?: boolean
  /** Edits keep the start and end; there is no duration shortcut. */
  allowDuration: boolean
  /** The server said this overlaps other study time: ask what to do. */
  overlap: boolean
  /** The server said the entry is more than 60 days old: ask for a tick. */
  needsConfirm: boolean
  /** Pomodoro rounds keep their times. */
  timesLocked?: boolean
}

/** Fields shared by "Add time" and "Edit session". All state lives in the container. */
export function SessionForm({
  values,
  onChange,
  errors,
  subjects,
  chapters,
  subjectsLoading,
  chaptersLoading,
  allowDuration,
  overlap,
  needsConfirm,
  timesLocked,
}: Props) {
  const id = useId()
  return (
    <div className="space-y-4">
      {allowDuration ? (
        <SegmentedControl<EntryMode>
          label="How to enter the time"
          value={values.mode}
          onValueChange={(mode) => onChange({ mode })}
          options={[
            { value: 'range', label: 'Start and end' },
            { value: 'duration', label: 'Start and duration' },
          ]}
        />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Started"
          type="datetime-local"
          value={values.start}
          disabled={timesLocked}
          onChange={(e) => onChange({ start: e.target.value })}
          hint={friendlyDateTime(values.start) || undefined}
          error={errors.start}
        />
        {values.mode === 'range' ? (
          <TextField
            label="Finished"
            type="datetime-local"
            value={values.end}
            disabled={timesLocked}
            onChange={(e) => onChange({ end: e.target.value })}
            hint={friendlyDateTime(values.end) || undefined}
            error={errors.end}
          />
        ) : (
          <DurationField
            label="Duration"
            valueMinutes={values.durationMinutes}
            onChangeMinutes={(durationMinutes) => onChange({ durationMinutes })}
            maxMinutes={MAX_MANUAL_SPAN_SECONDS / 60}
            error={errors.duration}
          />
        )}
      </div>

      <ContextPicker
        subjects={subjects}
        chapters={chapters}
        subjectsLoading={subjectsLoading}
        chaptersLoading={chaptersLoading}
        value={{ subject_id: values.subject_id, chapter_id: values.chapter_id, activity_type: values.activity_type }}
        onChange={onChange}
      />

      <div className="space-y-1.5">
        <Label htmlFor={`${id}-note`}>Note (optional)</Label>
        <Textarea
          id={`${id}-note`}
          rows={2}
          maxLength={NOTE_MAX_CHARS}
          value={values.note}
          aria-invalid={errors.note ? true : undefined}
          onChange={(e) => onChange({ note: e.target.value })}
        />
        {errors.note ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {errors.note}
          </p>
        ) : null}
      </div>

      {overlap ? (
        <fieldset className="space-y-2 rounded-xl border border-input bg-secondary p-4">
          <legend className="px-1 text-sm font-semibold">This overlaps other study time</legend>
          <SegmentedControl<'trim' | 'keep' | 'reject'>
            label="What to do about the overlap"
            value={values.onOverlap ?? 'reject'}
            onValueChange={(onOverlap) => onChange({ onOverlap })}
            options={[
              { value: 'trim', label: 'Keep the free part' },
              { value: 'keep', label: 'Keep both' },
              { value: 'reject', label: 'Cancel' },
            ]}
          />
          <p className="text-sm text-muted-foreground">
            Keeping both counts the overlapping minutes twice, so they are flagged in your log.
          </p>
        </fieldset>
      ) : null}

      {needsConfirm ? (
        <div className="flex items-start gap-3">
          <Checkbox
            id={`${id}-confirm`}
            checked={values.confirmOld}
            onCheckedChange={(c) => onChange({ confirmOld: c === true })}
          />
          <Label htmlFor={`${id}-confirm`} className="leading-snug">
            This is more than 60 days ago. I confirm the date is right.
          </Label>
        </div>
      ) : null}
    </div>
  )
}
