import { Button, Card, FileText, RotateCcw, Trash2 } from '@artha/design-system'

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
    <ul aria-label="PDFs in the trash" className="space-y-3">
      {items.map((doc) => {
        const left = daysLeft(doc.purge_after)
        const title = doc.title.trim() || doc.original_filename || 'Untitled PDF'
        return (
          <li key={doc.id}>
            <Card className="flex flex-wrap items-center gap-3 p-4">
              <FileText aria-hidden className="size-5 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <h3 className="font-display text-lg font-bold break-words">{title}</h3>
                <p className="text-xs text-muted-foreground">
                  {formatBytes(doc.bytes)}. Deleted {formatDate(doc.deleted_at)}.{' '}
                  {left > 0 ? `Removed for good in ${pluralize(left, 'day')}.` : 'Will be removed for good today.'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  disabled={!online || busyId === doc.id}
                  onClick={() => onRestore(doc)}
                  aria-label={`Restore ${title}`}
                >
                  <RotateCcw aria-hidden /> Restore
                </Button>
                <Button
                  variant="ghost"
                  disabled={!online || busyId === doc.id}
                  onClick={() => onDeleteNow(doc)}
                  aria-label={`Delete ${title} now`}
                >
                  <Trash2 aria-hidden /> Delete now
                </Button>
              </div>
            </Card>
          </li>
        )
      })}
    </ul>
  )
}
