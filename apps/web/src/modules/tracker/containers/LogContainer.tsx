import { Alert, Button, Download, PageHeader, SelectField, TableToolbar, TextField } from '@artha/design-system'
import { useState } from 'react'

import { ChapterField } from '~/modules/coverage'

import { useChapterOptionsState, useSubjectOptions } from '../hooks/useTagOptions'
import { useSessionsPage, useTrackerSettings } from '../hooks/useTrackerQueries'
import { downloadCsv } from '../lib/api'
import { notify } from '../lib/notify'
import { SessionsPanel } from './SessionsPanel'
import { TrackerShell } from './TrackerShell'

function Log({ tz }: { tz: string }) {
  const settings = useTrackerSettings().data
  const subjects = useSubjectOptions()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  // No chapter id means "All chapters": the whole subject, so the subject filter alone applies.
  const [chapter, setChapter] = useState<string | null>(null)
  const { options: chapters, loading: chaptersLoading } = useChapterOptionsState(subject || null)
  const filters = {
    ...(from ? { from } : {}),
    ...(to ? { to } : {}),
    ...(subject ? { subject_id: subject } : {}),
    ...(subject && chapter ? { chapter_id: chapter } : {}),
    include_notes: true,
  }
  const q = useSessionsPage(filters)
  const rows = q.data?.pages.flatMap((p) => p.results) ?? []
  return (
    <>
      <PageHeader
        title="Session log"
        description="Every session, newest first."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              notify.exportStarted('sessions CSV')
              void downloadCsv('/tracking/sessions/export.csv', { ...filters }, 'study-sessions.csv')
                .then(() => notify.exportFinished('sessions CSV'))
                .catch((e: unknown) => notify.error(e, 'Could not download your sessions.'))
            }}
          >
            <Download aria-hidden /> Download CSV
          </Button>
        }
      />
      <TableToolbar className="items-end">
        <TextField label="From" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" />
        <TextField label="To" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" />
        <div className="grid gap-1.5">
          <label htmlFor="log-subject" className="text-sm font-medium">
            Subject
          </label>
          <SelectField
            id="log-subject"
            value={subject}
            onValueChange={(next) => {
              setSubject(next)
              setChapter(null)
            }}
            options={[{ value: '', label: 'All subjects' }, ...subjects.map((s) => ({ value: s.id, label: s.name }))]}
          />
        </div>
        <ChapterField
          id="log-chapter"
          disabled={!subject}
          loading={chaptersLoading}
          chapters={chapters}
          value={{ chapter_id: chapter, all_chapters: !chapter }}
          onChange={(next) => setChapter(next.chapter_id)}
        />
      </TableToolbar>
      {q.isError ? (
        <Alert variant="error">
          <span role="alert">We could not load your sessions.</span>
        </Alert>
      ) : rows.length > 0 ? (
        <SessionsPanel
          sessions={rows}
          tz={tz}
          defaultActivity={settings?.default_activity_type ?? 'other'}
          groupByDay
          label="Session log"
        />
      ) : null}
      {!q.isPending && rows.length === 0 && !q.isError ? (
        <p className="text-muted-foreground">No sessions match.</p>
      ) : null}
      {q.hasNextPage ? (
        <Button variant="outline" size="sm" onClick={() => void q.fetchNextPage()} disabled={q.isFetchingNextPage}>
          Load more
        </Button>
      ) : null}
    </>
  )
}

export function LogContainer() {
  return <TrackerShell>{(tz) => <Log tz={tz} />}</TrackerShell>
}
