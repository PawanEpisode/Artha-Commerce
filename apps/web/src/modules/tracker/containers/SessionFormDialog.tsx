import { Alert, Button, Dialog, DialogContent, DialogDescription, DialogTitle, useToast } from '@artha/design-system'
import { useEffect, useMemo, useState } from 'react'

import { SessionForm } from '../components/SessionForm'
import { useAddManual, useEditSession } from '../hooks/useSessionActions'
import { useChapterOptions, useSubjectOptions } from '../hooks/useTagOptions'
import { errorCode, errorMessage, newClientId } from '../lib/api'
import { nowMs } from '../lib/clock'
import { fromLocalInput, toLocalInput } from '../lib/duration'
import { type FormErrors, type SessionFormValues, toEdit, toManualInput, validateForm } from '../lib/sessionForm'
import type { ActivityType, StudySession } from '../lib/types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  tz: string
  /** Set to edit a session; leave out to add time by hand. */
  session?: StudySession
  defaultActivity: ActivityType
}

function initial(tz: string, session: StudySession | undefined, defaultActivity: ActivityType): SessionFormValues {
  if (session) {
    return {
      mode: 'range',
      start: toLocalInput(Date.parse(session.started_at), tz),
      end: toLocalInput(Date.parse(session.ended_at), tz),
      durationMinutes: Math.round(session.focus_seconds / 60),
      subject_id: session.subject_id,
      chapter_id: session.chapter_id,
      activity_type: session.activity_type,
      note: session.note ?? '',
      onOverlap: null,
      confirmOld: false,
    }
  }
  // A fresh entry starts an hour back and runs to now, rounded to the minute: the common "I just studied" case.
  const end = nowMs()
  return {
    mode: 'duration',
    start: toLocalInput(end - 3600_000, tz),
    end: toLocalInput(end, tz),
    durationMinutes: 60,
    subject_id: null,
    chapter_id: null,
    activity_type: defaultActivity,
    note: '',
    onOverlap: null,
    confirmOld: false,
  }
}

/** Add time by hand, or edit a logged session. Server rules (overlap, old dates) are asked about, not hidden. */
export function SessionFormDialog({ open, onOpenChange, tz, session, defaultActivity }: Props) {
  const editing = !!session
  const [values, setValues] = useState(() => initial(tz, session, defaultActivity))
  const [errors, setErrors] = useState<FormErrors>({})
  const [overlap, setOverlap] = useState(false)
  const [needsConfirm, setNeedsConfirm] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  // One idempotency key per opening of the form: pressing Save twice, or a retry after a lost reply, adds one entry.
  const [clientId, setClientId] = useState(newClientId)
  const subjects = useSubjectOptions()
  const chapters = useChapterOptions(values.subject_id)
  const add = useAddManual()
  const edit = useEditSession()
  const toast = useToast()
  const busy = add.isPending || edit.isPending

  useEffect(() => {
    if (!open) return
    setValues(initial(tz, session, defaultActivity))
    setErrors({})
    setOverlap(false)
    setNeedsConfirm(false)
    setMessage(null)
    setClientId(newClientId())
  }, [open, tz, session, defaultActivity])

  const apply = useMemo(() => (patch: Partial<SessionFormValues>) => setValues((v) => ({ ...v, ...patch })), [])

  const fail = (error: unknown) => {
    const code = errorCode(error)
    if (code === 'overlap') {
      setOverlap(true)
      setValues((v) => ({ ...v, onOverlap: v.onOverlap ?? 'trim' }))
      setMessage('That time overlaps other study time. Choose what to do below, then save again.')
    } else if (code === 'confirmation_required') {
      setNeedsConfirm(true)
      setMessage('Please confirm the date below, then save again.')
    } else setMessage(errorMessage(error))
  }

  const submit = () => {
    const found = validateForm(values, tz, nowMs())
    setErrors(found)
    if (Object.keys(found).length > 0) return
    setMessage(null)
    if (editing && session) {
      const patch = toEdit(values, tz, session)
      if (Object.keys(patch).length === 0) return onOpenChange(false)
      edit.mutate(
        { id: session.id, patch },
        {
          onSuccess: () => {
            toast.show({ message: 'Session updated.' })
            onOpenChange(false)
          },
          onError: fail,
        },
      )
      return
    }
    add.mutate(toManualInput(values, tz, clientId), {
      onSuccess: ({ queued }) => {
        toast.show({
          message: queued ? 'Saved on this device. It will sync when you are back online.' : 'Study time added.',
        })
        onOpenChange(false)
      },
      onError: fail,
    })
  }

  const startMs = values.start ? fromLocalInput(values.start, tz).getTime() : 0
  const isOld = !!startMs && nowMs() - startMs > 60 * 86_400_000

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{editing ? 'Edit session' : 'Add study time'}</DialogTitle>
        <DialogDescription>
          {editing
            ? 'Changes are kept in your history, so you can always see what was edited.'
            : 'For time you studied away from the timer.'}
        </DialogDescription>
        <form
          className="mt-4 space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <SessionForm
            values={values}
            onChange={apply}
            errors={errors}
            subjects={subjects}
            chapters={chapters}
            allowDuration={!editing}
            overlap={overlap}
            needsConfirm={needsConfirm || isOld}
            timesLocked={session?.source === 'pomodoro'}
          />
          {message ? (
            <Alert variant="error">
              <span role="alert">{message}</span>
            </Alert>
          ) : null}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {editing ? 'Save changes' : 'Add time'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
