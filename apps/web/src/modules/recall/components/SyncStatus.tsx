import { Alert, Button, SyncChip } from '@artha/design-system'

import type { FlushResult } from '../lib/sync'

interface Props {
  pending: number
  syncing: boolean
  online: boolean
  last: FlushResult | null
  onRetry?: () => void
}

/** What could not be counted when reviews were sent: said once, in words, with the reason. */
export function conflictSentences(r: FlushResult | null): string[] {
  if (!r) return []
  const out: string[] = []
  if (r.stale > 0)
    out.push(
      `${r.stale === 1 ? '1 review was' : `${r.stale} reviews were`} not counted because the card was reworded after you answered.`,
    )
  if (r.late > 0)
    out.push(
      `${r.late === 1 ? '1 review was' : `${r.late} reviews were`} too old to count. Reviews sync for up to 30 days.`,
    )
  if (r.deleted > 0)
    out.push(`${r.deleted === 1 ? '1 review was' : `${r.deleted} reviews were`} for cards you deleted elsewhere.`)
  return out
}

/** Save status for the review screens: saved, saving, offline with a count, or needs attention with the reasons. */
export function SyncStatus({ pending, syncing, online, last, onRetry }: Props) {
  const notes = conflictSentences(last)
  const state = !online
    ? 'offline'
    : syncing
      ? 'saving'
      : pending > 0
        ? 'offline'
        : notes.length > 0
          ? 'attention'
          : 'saved'
  const count = !online || pending > 0 ? pending : notes.length
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <SyncChip state={state} count={count} />
        {online && pending > 0 && !syncing && onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry}>
            Sync now
          </Button>
        ) : null}
      </div>
      {notes.length > 0 ? (
        <Alert variant="info">
          <span role="status">{notes.join(' ')}</span>
        </Alert>
      ) : null}
      {last?.failure === 'throttled' ? (
        <p role="status" className="text-sm text-muted-foreground">
          Syncing is paused for a moment. Your reviews are safe on this device.
        </p>
      ) : null}
    </div>
  )
}
