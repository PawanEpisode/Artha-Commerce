import {
  Button,
  DataTable,
  RotateCcw,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'

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
    <DataTable aria-label="Notes in the trash">
      <TableHeader>
        <TableRow>
          <TableHead>Title</TableHead>
          <TableHead>Kept for</TableHead>
          <TableHead className="w-px">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((note) => {
          const left = daysLeft(note.purge_after)
          const title = note.title.trim() || 'Untitled note'
          return (
            <TableRow key={note.id}>
              <TableCell className="min-w-48 py-2 whitespace-normal">
                <p className="font-medium break-words">{title}</p>
                {note.snippet ? <p className="line-clamp-1 text-xs text-muted-foreground">{note.snippet}</p> : null}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                <span className="block">Deleted {formatDate(note.deleted_at)}.</span>
                <span className="block">
                  {left > 0 ? `Removed for good in ${pluralize(left, 'day')}.` : 'Will be removed for good today.'}
                </span>
              </TableCell>
              <TableCell className="w-px text-right">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!online || restoringId === note.id}
                  onClick={() => onRestore(note)}
                  aria-label={`Restore ${title}`}
                >
                  <RotateCcw aria-hidden /> Restore
                </Button>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </DataTable>
  )
}
