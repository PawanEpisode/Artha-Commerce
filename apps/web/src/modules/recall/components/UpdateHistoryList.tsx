import { Alert, Badge, Skeleton } from '@artha/design-system'

import { countsText, dayText, triggerLabel, versionsText } from '../lib/history'
import type { UpdateHistoryRow } from '../lib/schemas'
import { LoadError } from './RecallShell'

interface Props {
  rows: UpdateHistoryRow[] | undefined
  loading: boolean
  failed: boolean
  onRetry: () => void
}

/** The updates she has received on one deck, newest first: when, which versions, how it came, and what it did to her cards. */
export function UpdateHistoryList({ rows, loading, failed, onRetry }: Props) {
  if (loading) {
    return (
      <div aria-busy="true">
        <span className="sr-only" role="status">
          Loading your past updates…
        </span>
        <Skeleton className="h-20 w-full" />
      </div>
    )
  }
  if (failed || !rows) return <LoadError what="your past updates" onRetry={onRetry} />
  if (rows.length === 0) {
    return (
      <Alert variant="info">No updates yet. When this deck changes, what it did to your cards is listed here.</Alert>
    )
  }
  return (
    <ol className="space-y-3" aria-label="Past updates">
      {rows.map((r) => (
        <li key={r.id} className="space-y-1 rounded-xl border border-border bg-card p-3 text-sm">
          <p className="flex flex-wrap items-center gap-2 font-semibold">
            {dayText(r.applied_at)}
            <Badge variant="outline">{triggerLabel(r.trigger)}</Badge>
          </p>
          <p className="text-muted-foreground">{versionsText(r)}</p>
          {r.changelog_md ? <p className="break-words whitespace-pre-line">{r.changelog_md}</p> : null}
          <p>{countsText(r.counts)}</p>
        </li>
      ))}
    </ol>
  )
}
