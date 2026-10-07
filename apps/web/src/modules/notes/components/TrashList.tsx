import { Button, Card, RotateCcw } from '@artha/design-system'

import { daysLeft, formatDate, pluralize } from '../lib/format'
import type { NoteSummary } from '../lib/types'

interface TrashListProps {
  items: readonly NoteSummary[]
  onRestore: (note: NoteSummary) => void
  restoringId?: string
  online: boolean
}

/** Notes in the 30 day trash: how long each one is kept, and Restore. Restoring needs a connection. */
export function TrashList({ items, onRestore, restoringId, online }: TrashListProps) {
  return (
    <ul aria-label="Notes in the trash" className="space-y-3">
      {items.map((note) => {
        const left = daysLeft(note.purge_after)
        const title = note.title.trim() || 'Untitled note'
        return (
          <li key={note.id}>
            <Card className="flex flex-wrap items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <h3 className="font-display text-lg font-bold break-words">{title}</h3>
                {note.snippet ? <p className="line-clamp-1 text-sm text-muted-foreground">{note.snippet}</p> : null}
                <p className="text-xs text-muted-foreground">
                  Deleted {formatDate(note.deleted_at)}.{' '}
                  {left > 0 ? `Removed for good in ${pluralize(left, 'day')}.` : 'Will be removed for good today.'}
                </p>
              </div>
              <Button
                variant="outline"
                disabled={!online || restoringId === note.id}
                onClick={() => onRestore(note)}
                aria-label={`Restore ${title}`}
              >
                <RotateCcw aria-hidden /> Restore
              </Button>
            </Card>
          </li>
        )
      })}
    </ul>
  )
}
