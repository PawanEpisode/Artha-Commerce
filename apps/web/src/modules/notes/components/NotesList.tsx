import {
  Alert,
  Button,
  CloudOff,
  DataTable,
  Skeleton,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import type { ReactNode } from 'react'

import type { AggregateItem, NoteSummary } from '../lib/types'
import { noteColumnCount, NoteRow } from './NoteRow'

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
  /** A full width row after a note (an inline suggestion bar for the unfiled inbox). */
  renderExtra?: (note: NoteSummary) => ReactNode
  /** How a mark or a document row is drawn: a `TableRow` with the same columns (notes always use `NoteRow`). */
  renderOther?: (row: Exclude<ListRow, NoteSummary>) => ReactNode
}

/** A table of notes with all four states: loading, error with retry, empty, and the rows with "Load more". */
export function NotesList({
  label,
  items,
  isPending,
  isError,
  onRetry,
  empty,
  offline,
  showLocation = true,
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
      <div aria-busy="true" className="space-y-1.5">
        <span role="status" className="sr-only">
          Loading {label}…
        </span>
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
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
  const columns = noteColumnCount(showLocation)
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
        <DataTable aria-label={label}>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              {showLocation ? <TableHead>Filed under</TableHead> : null}
              <TableHead className="hidden md:table-cell">Tags</TableHead>
              <TableHead className="text-right">Updated</TableHead>
              <TableHead className="w-px">
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((row) =>
              isNoteRow(row) ? (
                <NoteBlock
                  key={row.id}
                  columns={columns}
                  extra={renderExtra?.(row)}
                  note={row}
                  showLocation={showLocation}
                  onPin={onPin ? (pinned) => onPin(row, pinned) : undefined}
                  onTrash={onTrash ? () => onTrash(row) : undefined}
                />
              ) : (
                <RowFragment key={`${row.type}-${row.id}`}>
                  {renderOther?.(row as Exclude<ListRow, NoteSummary>)}
                </RowFragment>
              ),
            )}
          </TableBody>
        </DataTable>
      )}
      {hasMore && onLoadMore ? (
        <Button variant="outline" size="sm" onClick={onLoadMore} disabled={loadingMore}>
          {loadingMore ? 'Loading…' : 'Load more'}
        </Button>
      ) : null}
    </div>
  )
}

const RowFragment = ({ children }: { children: ReactNode }) => <>{children}</>

function NoteBlock({
  columns,
  extra,
  ...rest
}: {
  columns: number
  extra: ReactNode
  note: NoteSummary
  showLocation: boolean
  onPin?: (pinned: boolean) => void
  onTrash?: () => void
}) {
  return (
    <>
      <NoteRow {...rest} />
      {extra ? (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={columns} className="h-auto bg-muted/30 py-1.5">
            {extra}
          </TableCell>
        </TableRow>
      ) : null}
    </>
  )
}
