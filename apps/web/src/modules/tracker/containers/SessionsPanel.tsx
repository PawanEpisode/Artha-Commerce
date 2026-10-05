import { Alert, Button, EmptyState, Merge, SelectField } from '@artha/design-system'
import { useState } from 'react'

import { SessionRow } from '../components/SessionRow'
import { useDeleteSession, useMerge, useUndo } from '../hooks/useSessionActions'
import { errorCode, errorMessage } from '../lib/api'
import { notify } from '../lib/notify'
import type { ActivityType, StudySession } from '../lib/types'
import { SessionFormDialog } from './SessionFormDialog'
import { SplitDialog } from './SplitDialog'

/** A list of sessions with edit, split, delete (with undo) and merge. Used by Today, a day's detail and the log. */
export function SessionsPanel({
  sessions,
  tz,
  defaultActivity,
  emptyText = 'Nothing logged yet.',
}: {
  sessions: StudySession[]
  tz: string
  defaultActivity: ActivityType
  emptyText?: string
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<StudySession | null>(null)
  const [splitting, setSplitting] = useState<StudySession | null>(null)
  const [mergeError, setMergeError] = useState<string | null>(null)
  const [needsChoice, setNeedsChoice] = useState(false)
  const [keepSubject, setKeepSubject] = useState('')
  const del = useDeleteSession()
  const undo = useUndo()
  const merge = useMerge()

  const chosen = sessions.filter((s) => selected.has(s.id))
  const toggle = (id: string, on: boolean) =>
    setSelected((cur) => {
      const next = new Set(cur)
      if (on) next.add(id)
      else next.delete(id)
      return next
    })

  const restore = (vars: Parameters<typeof undo.mutate>[0], then: string) =>
    undo.mutate(vars, { onSuccess: () => notify.undone(), onError: (e) => notify.error(e, then) })

  const remove = (s: StudySession) =>
    del.mutate(s.id, {
      onSuccess: (r) =>
        notify.sessionDeleted(s.focus_seconds, () =>
          // The note is not kept in the history, so the page sends it back with the undo.
          restore(
            { token: r.undo_token, notes: s.note ? { [s.id]: s.note } : undefined },
            'Could not restore the session.',
          ),
        ),
      onError: (e) => notify.error(e, 'Could not delete the session.'),
    })

  const runMerge = (subjectId?: string) => {
    setMergeError(null)
    const subject = chosen.find((s) => s.subject_id === subjectId)
    merge.mutate(
      {
        session_ids: chosen.map((s) => s.id),
        ...(subjectId ? { subject_id: subjectId, chapter_id: subject?.chapter_id ?? null } : {}),
      },
      {
        onSuccess: (r) => {
          setSelected(new Set())
          setNeedsChoice(false)
          const token = r.undo_token
          notify.sessionsMerged(
            chosen.length,
            token ? () => restore({ token }, 'Could not undo the merge.') : undefined,
          )
        },
        onError: (e) => {
          if (errorCode(e) === 'choice_required') {
            setNeedsChoice(true)
            setKeepSubject(chosen.find((s) => s.subject_id)?.subject_id ?? '')
          } else setMergeError(errorMessage(e))
        },
      },
    )
  }

  if (sessions.length === 0) return <EmptyState title={emptyText} />

  return (
    <div className="space-y-3">
      {chosen.length >= 2 ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-input bg-secondary p-3">
          <span className="text-sm font-medium">{chosen.length} selected</span>
          {needsChoice ? (
            <>
              <div className="flex items-center gap-2 text-sm">
                <label htmlFor="merge-subject" className="font-medium">
                  Keep subject
                </label>
                <SelectField
                  id="merge-subject"
                  value={keepSubject}
                  onValueChange={setKeepSubject}
                  className="w-48"
                  options={[...new Map(chosen.filter((s) => s.subject_id).map((s) => [s.subject_id, s])).values()].map(
                    (s) => ({ value: s.subject_id as string, label: s.subject_name }),
                  )}
                />
              </div>
              <Button onClick={() => runMerge(keepSubject)} disabled={merge.isPending}>
                Merge
              </Button>
            </>
          ) : (
            <Button onClick={() => runMerge()} disabled={merge.isPending}>
              <Merge aria-hidden /> Merge
            </Button>
          )}
          <Button variant="outline" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </div>
      ) : null}
      {mergeError ? (
        <Alert variant="error">
          <span role="alert">{mergeError}</span>
        </Alert>
      ) : null}
      <ul className="space-y-2">
        {sessions.map((s) => (
          <SessionRow
            key={s.id}
            session={s}
            tz={tz}
            selected={selected.has(s.id)}
            onSelect={(on) => toggle(s.id, on)}
            onEdit={() => setEditing(s)}
            onSplit={() => setSplitting(s)}
            onDelete={() => remove(s)}
          />
        ))}
      </ul>
      {editing ? (
        <SessionFormDialog
          open
          onOpenChange={(o) => !o && setEditing(null)}
          tz={tz}
          session={editing}
          defaultActivity={defaultActivity}
        />
      ) : null}
      <SplitDialog session={splitting} tz={tz} onClose={() => setSplitting(null)} />
    </div>
  )
}
