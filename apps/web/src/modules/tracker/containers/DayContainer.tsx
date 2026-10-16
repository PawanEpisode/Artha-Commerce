import { Alert, ArrowLeft, Button, PageHeader, Plus } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { useSessionsPage, useTrackerSettings } from '../hooks/useTrackerQueries'
import { formatDuration } from '../lib/duration'
import { dayLabel } from '../lib/format'
import { SessionFormDialog } from './SessionFormDialog'
import { SessionsPanel } from './SessionsPanel'
import { TrackerShell } from './TrackerShell'

function Day({ date, tz }: { date: string; tz: string }) {
  const settings = useTrackerSettings().data
  const [adding, setAdding] = useState(false)
  const q = useSessionsPage({ from: date, to: date, include_notes: true })
  const rows = q.data?.pages.flatMap((p) => p.results) ?? []
  const total = rows.reduce((s, r) => s + r.focus_seconds, 0)
  return (
    <>
      <PageHeader
        eyebrow={
          <Link to="/app/tracker/reports" className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="size-3" aria-hidden /> Back to reports
          </Link>
        }
        title={dayLabel(date)}
        description={`${formatDuration(total)} over ${rows.length} ${rows.length === 1 ? 'session' : 'sessions'}`}
        actions={
          <Button variant="outline" size="sm" onClick={() => setAdding(true)}>
            <Plus aria-hidden /> Add time
          </Button>
        }
      />
      {q.isError ? (
        <Alert variant="error">
          <span role="alert">We could not load this day.</span>
        </Alert>
      ) : (
        <SessionsPanel
          sessions={rows}
          tz={tz}
          defaultActivity={settings?.default_activity_type ?? 'other'}
          emptyText="No study time on this day."
          label="Sessions on this day"
        />
      )}
      <SessionFormDialog
        open={adding}
        onOpenChange={setAdding}
        tz={tz}
        defaultActivity={settings?.default_activity_type ?? 'other'}
      />
    </>
  )
}

export function DayContainer({ date }: { date: string }) {
  return <TrackerShell>{(tz) => <Day date={date} tz={tz} />}</TrackerShell>
}
