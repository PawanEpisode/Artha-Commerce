import { Alert, Button, ButtonLink, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { RecallShell } from '../components/RecallShell'
import { SessionSummary } from '../components/SessionSummary'
import { useSessionSummary } from '../hooks/useSessionSummary'
import { useSync } from '../hooks/useSync'

function Summary({ sessionId }: { sessionId: string }) {
  const sync = useSync()
  const { data, loading, offline } = useSessionSummary(sessionId, sync.pending === 0 && !sync.syncing)
  if (loading) {
    return (
      <div aria-busy="true" className="space-y-4">
        <span className="sr-only" role="status">
          Loading your summary…
        </span>
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (!data) {
    return (
      <Alert variant="info">
        <span className="flex flex-wrap items-center gap-3">
          We could not find that session on this device.
          <ButtonLink variant="outline" asChild>
            <Link to="/app/recall">Back to revision</Link>
          </ButtonLink>
        </span>
      </Alert>
    )
  }
  return (
    <SessionSummary
      data={data}
      offline={offline}
      actions={
        <>
          <ButtonLink asChild>
            <Link to="/app/recall">Back to revision</Link>
          </ButtonLink>
          <Button variant="outline" asChild>
            <Link to="/app/recall/review" search={{ source: 'today', ahead: true }}>
              Review ahead 10 cards
            </Link>
          </Button>
          <ButtonLink variant="ghost" asChild>
            <Link to="/app/recall/stats">See my stats</Link>
          </ButtonLink>
        </>
      }
    />
  )
}

export function SummaryContainer({ sessionId }: { sessionId: string }) {
  return (
    <RecallShell>
      <Summary sessionId={sessionId} />
    </RecallShell>
  )
}
