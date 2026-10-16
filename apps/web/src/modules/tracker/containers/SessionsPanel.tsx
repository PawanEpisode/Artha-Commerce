import {
  Alert,
  Button,
  DataTable,
  EmptyState,
  Merge,
  SelectField,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Fragment, useState } from 'react'

import { SessionRow } from '../components/SessionRow'
import { useDeleteSession, useMerge, useUndo } from '../hooks/useSessionActions'
import { errorCode, errorMessage } from '../lib/api'
import { formatDuration } from '../lib/duration'
import { dayLabel } from '../lib/format'
import { notify } from '../lib/notify'
import type { ActivityType, StudySession } from '../lib/types'
import { SessionFormDialog } from './SessionFormDialog'
import { SplitDialog } from './SplitDialog'

/**
 * Sessions as a dense table with edit, split, delete (with undo) and merge. Used by Today, a day's detail, the log and the focus
 * history. With `groupByDay` one table carries a day heading row (date and total) above each day's sessions.
 */
export function SessionsPanel({
  sessions,
  tz,
  defaultActivity,
  emptyText = 'Nothing logged yet.',
  groupByDay = false,
  label = 'Sessions',
}: {
  sessions: StudySession[]
  tz: string
  defaultActivity: ActivityType
  emptyText?: string
  groupByDay?: boolean
  /** Accessible name of the table. */
  label?: string
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
  const selectedDay = chosen[0]?.study_date
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

  if (sessions.length === 0) return <EmptyState className="rounded-lg py-6" title={emptyText} />

  return (
    <div className="space-y-2">
      {chosen.length >= 2 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-input bg-secondary p-2">
          <span className="pl-1 text-[13px] font-medium">{chosen.length} selected</span>
          {needsChoice ? (
            <>
              <div className="flex items-center gap-2 text-[13px]">
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
              <Button size="sm" onClick={() => runMerge(keepSubject)} disabled={merge.isPending}>
                Merge
              </Button>
            </>
          ) : (
            <Button size="sm" onClick={() => runMerge()} disabled={merge.isPending}>
              <Merge aria-hidden /> Merge
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </div>
      ) : null}
      {mergeError ? (
        <Alert variant="error">
          <span role="alert">{mergeError}</span>
        </Alert>
      ) : null}
      <DataTable aria-label={label}>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8 pr-0">
              <span className="sr-only">Select</span>
            </TableHead>
            <TableHead>Time</TableHead>
            <TableHead>Subject</TableHead>
            <TableHead className="hidden sm:table-cell">Activity</TableHead>
            <TableHead className="hidden md:table-cell">Source</TableHead>
            <TableHead className="text-right">Counted</TableHead>
            <TableHead className="w-8 pl-0">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sessions.map((s, i) => (
            <Fragment key={s.id}>
              {groupByDay && s.study_date !== sessions[i - 1]?.study_date ? (
                <tr className="border-b bg-muted/40">
                  <th
                    scope="colgroup"
                    colSpan={7}
                    className="h-8 px-3.5 text-left text-[13px] font-semibold text-foreground"
                  >
                    <span className="flex items-baseline justify-between gap-3">
                      <span>{dayLabel(s.study_date)}</span>
                      <span className="font-medium text-muted-foreground tabular-nums">
                        {formatDuration(
                          sessions
                            .filter((x) => x.study_date === s.study_date)
                            .reduce((n, x) => n + x.focus_seconds, 0),
                        )}
                      </span>
                    </span>
                  </th>
                </tr>
              ) : null}
              <SessionRow
                session={s}
                tz={tz}
                selected={selected.has(s.id)}
                selectDisabled={selectedDay !== undefined && s.study_date !== selectedDay}
                onSelect={(on) => toggle(s.id, on)}
                onEdit={() => setEditing(s)}
                onSplit={() => setSplitting(s)}
                onDelete={() => remove(s)}
              />
            </Fragment>
          ))}
        </TableBody>
      </DataTable>
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
