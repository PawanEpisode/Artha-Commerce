import { Alert, Button, CloudOff, Skeleton } from '@artha/design-system'
import type { ReactNode } from 'react'

import type { AggregateItem, NoteSummary } from '../lib/types'
import { NoteCard } from './NoteCard'

/** A row of the list: a note, or (R2) a mark or a document from the aggregate feed. */
export type ListRow = NoteSummary | AggregateItem
const isNoteRow = (row: ListRow): row is NoteSummary => !('type' in row) || row.type === 'note'

interface NotesListProps {
  label: string
  items: readonly ListRow[]
  isPending: boolean
  isError: boolean
  onRetry: () => void
  /** Shown when the list loaded and is empty. */
  empty: ReactNode
  /** The list is what this device kept, not what the server holds. */
  offline?: boolean
  showLocation?: boolean
  hasMore?: boolean
  loadingMore?: boolean
  onLoadMore?: () => void
  onPin?: (note: NoteSummary, pinned: boolean) => void
  onTrash?: (note: NoteSummary) => void
  /** Rows to put before a note (an inline suggestion bar for the unfiled inbox). */
  renderExtra?: (note: NoteSummary) => ReactNode
  /** How a mark or a document row is drawn (notes always use the note card). */
  renderOther?: (row: Exclude<ListRow, NoteSummary>) => ReactNode
}

/** A list of notes with all four states: loading, error with retry, empty, and the items with "Load more". */
export function NotesList({
  label,
  items,
  isPending,
  isError,
  onRetry,
  empty,
  offline,
  showLocation,
  hasMore,
  loadingMore,
  onLoadMore,
  onPin,
  onTrash,
  renderExtra,
  renderOther,
}: NotesListProps) {
  if (isPending) {
    return (
      <div aria-busy="true" className="space-y-3">
        <span role="status" className="sr-only">
          Loading {label}…
        </span>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }
  if (isError && items.length === 0) {
    return (
      <Alert variant="error">
        <span className="flex flex-wrap items-center gap-3">
          <span>We could not load {label}.</span>
          <Button size="sm" variant="outline" onClick={onRetry}>
            Try again
          </Button>
        </span>
      </Alert>
    )
  }
  return (
    <div className="space-y-3">
      {offline ? (
        <Alert variant="info">
          <span className="flex items-center gap-2">
            <CloudOff aria-hidden className="size-4 shrink-0" />
            You are offline. Showing the notes kept on this device.
          </span>
        </Alert>
      ) : null}
      {items.length === 0 ? (
        empty
      ) : (
        <ul aria-label={label} className="space-y-3">
          {items.map((row) =>
            isNoteRow(row) ? (
              <li key={row.id} className="space-y-2">
                <NoteCard
                  note={row}
                  showLocation={showLocation}
                  onPin={onPin ? (pinned) => onPin(row, pinned) : undefined}
                  onTrash={onTrash ? () => onTrash(row) : undefined}
                />
                {renderExtra?.(row)}
              </li>
            ) : (
              <li key={`${row.type}-${row.id}`}>{renderOther?.(row as Exclude<ListRow, NoteSummary>)}</li>
            ),
          )}
        </ul>
      )}
      {hasMore && onLoadMore ? (
        <Button variant="outline" onClick={onLoadMore} disabled={loadingMore}>
          {loadingMore ? 'Loading…' : 'Load more'}
        </Button>
      ) : null}
    </div>
  )
}
