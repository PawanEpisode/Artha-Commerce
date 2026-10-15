import {
  addIsoDays,
  Button,
  DatePicker,
  Plus,
  SegmentedControl,
  SelectField,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  TextField,
} from '@artha/design-system'
import { useEffect, useRef, useState } from 'react'

import { useChapterOptionsState, useSubjectOptionsState } from '~/modules/tracker'

import { useMediaQuery } from '../hooks/useMediaQuery'
import type { TaskActions } from '../hooks/useTaskActions'
import { errorCode, errorDetails, errorMessage, newClientId } from '../lib/api'
import { OWN_EST_MAX, OWN_EST_MIN, OWN_TASK_MAX_DAYS_AHEAD, TITLE_MAX } from '../lib/limits'
import type { Plan } from '../lib/types'

const PRESETS = [5, 10, 20, 30, 45, 60]
type When = 'today' | 'tomorrow' | 'other'

export interface AddFormValues {
  title: string
  minutes: string
  when: When
  other: string | null
}

/** Field errors for the form, or an empty object when it can be sent. Pure, so it is tested without the sheet. */
export function validateAdd(v: AddFormValues, today: string): Partial<Record<'title' | 'minutes' | 'date', string>> {
  const errors: Partial<Record<'title' | 'minutes' | 'date', string>> = {}
  if (!v.title.trim()) errors.title = 'Give the task a title.'
  else if (v.title.trim().length > TITLE_MAX) errors.title = `Use at most ${TITLE_MAX} characters.`
  const mins = Number(v.minutes)
  if (!Number.isInteger(mins) || mins < OWN_EST_MIN || mins > OWN_EST_MAX)
    errors.minutes = `Minutes must be a whole number from ${OWN_EST_MIN} to ${OWN_EST_MAX}.`
  if (v.when === 'other') {
    if (!v.other) errors.date = 'Pick a day.'
    else if (v.other < today || v.other > addIsoDays(today, OWN_TASK_MAX_DAYS_AHEAD))
      errors.date = `Pick a day from today to ${OWN_TASK_MAX_DAYS_AHEAD} days ahead.`
  }
  return errors
}

export const dateOf = (v: AddFormValues, today: string): string =>
  v.when === 'today' ? today : v.when === 'tomorrow' ? addIsoDays(today, 1) : (v.other ?? today)

/** The add-your-own-task sheet (`?add=true`). Title, paper, chapter, minutes, day; errors inline; a retry reuses one client id. */
export function AddTaskSheet({
  open,
  plan,
  actions,
  onClose,
}: {
  open: boolean
  plan: Plan
  actions: TaskActions
  onClose: () => void
}) {
  const wide = useMediaQuery('(min-width: 768px)')
  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side={wide ? 'right' : 'bottom'}>
        {open ? <Form plan={plan} actions={actions} onClose={onClose} /> : null}
      </SheetContent>
    </Sheet>
  )
}

function Form({ plan, actions, onClose }: { plan: Plan; actions: TaskActions; onClose: () => void }) {
  const today = plan.date
  const clientId = useRef(newClientId())
  const [title, setTitle] = useState('')
  const [minutes, setMinutes] = useState('20')
  const [when, setWhen] = useState<When>('today')
  const [other, setOther] = useState<string | null>(null)
  const [subject, setSubject] = useState('')
  const [chapter, setChapter] = useState('')
  const [errors, setErrors] = useState<Partial<Record<'title' | 'minutes' | 'date' | 'form', string>>>({})
  const [saving, setSaving] = useState(false)
  const subjects = useSubjectOptionsState()
  const chapters = useChapterOptionsState(subject || null)
  useEffect(() => setChapter(''), [subject])

  const duplicate =
    plan.tasks.some((t) => t.origin === 'user' && t.title.trim().toLowerCase() === title.trim().toLowerCase()) &&
    title.trim() !== ''

  const submit = async () => {
    const values: AddFormValues = { title, minutes, when, other }
    const found = validateAdd(values, today)
    setErrors(found)
    if (Object.keys(found).length) return
    setSaving(true)
    try {
      const date = dateOf(values, today)
      await actions.add({
        client_id: clientId.current,
        title: title.trim(),
        est_minutes: Number(minutes),
        ...(date !== today ? { date } : {}),
        subject_id: subject || null,
        chapter_id: chapter || null,
      })
      onClose()
    } catch (error) {
      const details = errorDetails(error)
      const field = (k: string) => (Array.isArray(details[k]) ? String((details[k] as unknown[])[0]) : undefined)
      setErrors({
        title: field('title'),
        minutes: field('est_minutes'),
        date: field('date'),
        form:
          errorCode(error) === 'quota_exceeded'
            ? errorMessage(error, 'You have 20 tasks today. Move one to tomorrow or delete one.')
            : field('title') || field('est_minutes') || field('date')
              ? undefined
              : errorMessage(error, 'That did not save. Please try again.'),
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        void submit()
      }}
      noValidate
    >
      <SheetHeader>
        <SheetTitle>Add your own task</SheetTitle>
        <SheetDescription>It counts in today's ring and stays until you finish or move it.</SheetDescription>
      </SheetHeader>
      <div className="space-y-4">
        <TextField
          label="Title"
          value={title}
          maxLength={TITLE_MAX}
          onChange={(e) => setTitle(e.target.value)}
          error={errors.title}
          hint={duplicate ? 'You already have a task with this title today. You can still add it.' : undefined}
        />
        <div className="grid gap-2">
          <span className="text-sm font-medium" id="add-minutes-label">
            Minutes
          </span>
          <div role="group" aria-labelledby="add-minutes-label" className="flex flex-wrap gap-2">
            {PRESETS.map((m) => (
              <Button
                key={m}
                type="button"
                size="sm"
                variant={minutes === String(m) ? 'default' : 'outline'}
                aria-pressed={minutes === String(m)}
                onClick={() => setMinutes(String(m))}
              >
                {m}
              </Button>
            ))}
          </div>
          <TextField
            label="Or type minutes"
            type="number"
            inputMode="numeric"
            min={OWN_EST_MIN}
            max={OWN_EST_MAX}
            value={minutes}
            onChange={(e) => setMinutes(e.target.value)}
            error={errors.minutes}
          />
        </div>
        <SegmentedControl<When>
          label="Day"
          value={when}
          onValueChange={setWhen}
          stretch
          options={[
            { value: 'today', label: 'Today' },
            { value: 'tomorrow', label: 'Tomorrow' },
            { value: 'other', label: 'Pick a day' },
          ]}
        />
        {when === 'other' ? (
          <DatePicker
            label="Day"
            value={other}
            min={today}
            max={addIsoDays(today, OWN_TASK_MAX_DAYS_AHEAD)}
            onValueChange={setOther}
            error={errors.date}
          />
        ) : null}
        <div className="grid gap-2">
          <span className="text-sm font-medium" id="add-paper-label">
            Paper (optional)
          </span>
          <SelectField
            aria-label="Paper"
            value={subject}
            onValueChange={setSubject}
            loading={subjects.loading}
            options={[
              { value: '', label: 'No paper' },
              ...subjects.options.map((s) => ({ value: s.id, label: s.name })),
            ]}
          />
        </div>
        {subject ? (
          <div className="grid gap-2">
            <span className="text-sm font-medium">Chapter (optional)</span>
            <SelectField
              aria-label="Chapter"
              value={chapter}
              onValueChange={setChapter}
              loading={chapters.loading}
              options={[
                { value: '', label: 'No chapter' },
                ...chapters.options.map((c) => ({ value: c.id, label: c.name })),
              ]}
            />
          </div>
        ) : null}
        {errors.form ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {errors.form}
          </p>
        ) : null}
      </div>
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" loading={saving}>
          <Plus aria-hidden /> Add task
        </Button>
      </SheetFooter>
    </form>
  )
}
