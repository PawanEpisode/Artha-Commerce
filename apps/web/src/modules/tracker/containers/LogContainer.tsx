import { Alert, Button, Download, SelectField, TextField } from '@artha/design-system'
import { useState } from 'react'

import { useSubjectOptions } from '../hooks/useTagOptions'
import { useSessionsPage, useTrackerSettings } from '../hooks/useTrackerQueries'
import { downloadCsv } from '../lib/api'
import { dayLabel } from '../lib/format'
import { SessionsPanel } from './SessionsPanel'
import { TrackerShell } from './TrackerShell'

function Log({ tz }: { tz: string }) {
  const settings = useTrackerSettings().data
  const subjects = useSubjectOptions()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  const filters = {
    ...(from ? { from } : {}),
    ...(to ? { to } : {}),
    ...(subject ? { subject_id: subject } : {}),
    include_notes: true,
  }
  const q = useSessionsPage(filters)
  const rows = q.data?.pages.flatMap((p) => p.results) ?? []
  const days = [...new Set(rows.map((r) => r.study_date))]
  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold">Session log</h1>
          <p className="text-muted-foreground">Every session, newest first.</p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void downloadCsv('/tracking/sessions/export.csv', { ...filters }, 'study-sessions.csv')}
        >
          <Download aria-hidden /> Download CSV
        </Button>
      </header>
      <div className="grid gap-3 sm:grid-cols-3">
        <TextField label="From" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        <TextField label="To" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        <div className="grid gap-2">
          <label htmlFor="log-subject" className="text-sm font-medium">
            Subject
          </label>
          <SelectField
            id="log-subject"
            value={subject}
            onValueChange={setSubject}
            options={[{ value: '', label: 'All subjects' }, ...subjects.map((s) => ({ value: s.id, label: s.name }))]}
          />
        </div>
      </div>
      {q.isError ? (
        <Alert variant="error">
          <span role="alert">We could not load your sessions.</span>
        </Alert>
      ) : (
        days.map((day) => (
          <section key={day} aria-label={dayLabel(day)} className="space-y-2">
            <h2 className="text-base font-bold">{dayLabel(day)}</h2>
            <SessionsPanel
              sessions={rows.filter((r) => r.study_date === day)}
              tz={tz}
              defaultActivity={settings?.default_activity_type ?? 'other'}
            />
          </section>
        ))
      )}
      {!q.isPending && rows.length === 0 && !q.isError ? (
        <p className="text-muted-foreground">No sessions match.</p>
      ) : null}
      {q.hasNextPage ? (
        <Button variant="outline" onClick={() => void q.fetchNextPage()} disabled={q.isFetchingNextPage}>
          Load more
        </Button>
      ) : null}
    </>
  )
}

export function LogContainer() {
  return <TrackerShell>{(tz) => <Log tz={tz} />}</TrackerShell>
}
