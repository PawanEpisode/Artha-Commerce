import {
  Button,
  DataTable,
  FileText,
  RotateCcw,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Trash2,
} from '@artha/design-system'

import type { DocumentSummary } from '../../lib/document-types'
import { daysLeft, formatBytes, formatDate, pluralize } from '../../lib/format'

interface TrashedDocumentsProps {
  items: readonly DocumentSummary[]
  online: boolean
  busyId?: string
  onRestore: (doc: DocumentSummary) => void
  onDeleteNow: (doc: DocumentSummary) => void
}

/** PDFs in the 30 day trash: when each goes for good, Restore, and Delete now (which frees the space at once). */
export function TrashedDocuments({ items, online, busyId, onRestore, onDeleteNow }: TrashedDocumentsProps) {
  return (
    <DataTable aria-label="PDFs in the trash">
      <TableHeader>
        <TableRow>
          <TableHead>PDF</TableHead>
          <TableHead className="text-right">Size</TableHead>
          <TableHead>Kept for</TableHead>
          <TableHead className="w-px">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((doc) => {
          const left = daysLeft(doc.purge_after)
          const title = doc.title.trim() || doc.original_filename || 'Untitled PDF'
          return (
            <TableRow key={doc.id}>
              <TableCell className="min-w-48 whitespace-normal">
                <span className="flex items-start gap-2 font-medium break-words">
                  <FileText aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                  {title}
                </span>
              </TableCell>
              <TableCell className="text-right whitespace-nowrap text-muted-foreground tabular-nums">
                {formatBytes(doc.bytes)}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                <span className="block">Deleted {formatDate(doc.deleted_at)}.</span>
                <span className="block">
                  {left > 0 ? `Removed for good in ${pluralize(left, 'day')}.` : 'Will be removed for good today.'}
                </span>
              </TableCell>
              <TableCell className="w-px text-right whitespace-nowrap">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!online || busyId === doc.id}
                  onClick={() => onRestore(doc)}
                  aria-label={`Restore ${title}`}
                >
                  <RotateCcw aria-hidden /> Restore
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={!online || busyId === doc.id}
                  onClick={() => onDeleteNow(doc)}
                  aria-label={`Delete ${title} now`}
                >
                  <Trash2 aria-hidden /> Delete now
                </Button>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </DataTable>
  )
}
