import {
  Badge,
  Button,
  Download,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Ellipsis,
  FileDown,
  FileText,
  Pencil,
  ProgressBar,
  ScanText,
  TableCell,
  TableRow,
  Tag,
  Trash2,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { canOpenDocument, documentBadges, documentTitle, readPercent } from '../../lib/document-badges'
import type { DocumentSummary } from '../../lib/document-types'
import { formatBytes, formatDate, pluralize } from '../../lib/format'
import { type DocumentCardActions, LocationChips } from './DocumentCard'
import { DocumentCover } from './DocumentCover'
import { DocumentStatusBadge } from './DocumentStatusBadge'

interface DocumentRowProps extends DocumentCardActions {
  doc: DocumentSummary
  /** Hide the "filed under" cell when the page already says it. */
  showLocation?: boolean
  /** The library: a small cover, reading progress and the actions menu. Off in the notes tables (no cover, no menu). */
  full?: boolean
  /** The list came from this device while offline. */
  offlineCopy?: boolean
}

const SHARE_PRIVATE = new Set(['coaching', 'institute_material'])

/**
 * One PDF as a table row. Same five columns as a note row (title, filed under, tags, updated, actions) so PDFs, marks and
 * notes share a table in the subject and chapter views; the library turns on `full` for the cover, progress and menu.
 */
export function DocumentRow({
  doc,
  showLocation = true,
  full = false,
  offlineCopy,
  onEdit,
  onExport,
  onDownload,
  onTrash,
  onMakeSearchable,
}: DocumentRowProps) {
  const title = documentTitle(doc)
  const badges = documentBadges(doc, { offlineCopy })
  const percent = readPercent(doc)
  const openable = canOpenDocument(doc)
  const needsOcr =
    doc.status === 'ready' && doc.is_scanned === true && (doc.ocr_status === 'none' || doc.ocr_status === 'failed')
  const hasMenu = full && (onEdit || onExport || onDownload || onTrash)
  return (
    <TableRow data-slot="document-row" data-status={doc.status}>
      <TableCell className="min-w-56 py-2 whitespace-normal">
        <div className="flex items-start gap-2.5">
          {full ? <DocumentCover doc={doc} compact mini /> : null}
          {!full ? <FileText aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" /> : null}
          <div className="min-w-0 flex-1 space-y-0.5">
            <p className="truncate font-medium">
              {openable ? (
                <Link
                  to="/app/notes/pdf/$docId"
                  params={{ docId: doc.id }}
                  title={title}
                  className="underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  {title}
                </Link>
              ) : (
                <span title={title}>{title}</span>
              )}
            </p>
            <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-muted-foreground">
              <span>
                {doc.page_count ? pluralize(doc.page_count, 'page') : 'Pages not counted yet'} ·{' '}
                {formatBytes(doc.bytes)}
              </span>
              {badges.map((badge) => (
                <DocumentStatusBadge key={badge.kind} badge={badge} />
              ))}
              {full && SHARE_PRIVATE.has(doc.source_kind) ? (
                <Badge variant="outline" className="max-w-full min-w-0">
                  <span className="truncate">Private to you</span>
                </Badge>
              ) : null}
            </p>
            {full && percent !== null ? (
              <div className="flex items-center gap-2">
                <ProgressBar value={percent} label={`Read ${percent}%`} className="max-w-32 flex-1" />
                <span className="text-xs text-muted-foreground tabular-nums">Read {percent}%</span>
              </div>
            ) : null}
            {full && needsOcr && onMakeSearchable ? (
              <Button size="xs" variant="outline" onClick={() => onMakeSearchable(doc)}>
                <ScanText aria-hidden /> Make searchable
              </Button>
            ) : null}
          </div>
        </div>
      </TableCell>
      {showLocation ? (
        <TableCell className="max-w-56">
          <div className="flex min-w-0 flex-wrap items-center gap-1">
            <LocationChips doc={doc} />
            {doc.link.moved_or_removed ? (
              <Badge variant="outline" className="max-w-full min-w-0">
                <span className="truncate">Chapter moved or removed</span>
              </Badge>
            ) : null}
          </div>
        </TableCell>
      ) : null}
      <TableCell className="hidden md:table-cell">
        <div className="flex max-w-56 min-w-0 flex-wrap items-center gap-1">
          {doc.tags.map((tag) => (
            <Badge key={tag.id} variant="outline" className="max-w-full min-w-0" title={tag.name}>
              <Tag aria-hidden className="shrink-0" />
              <span className="truncate">{tag.name}</span>
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell className="text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums">
        <time dateTime={doc.updated_at}>{formatDate(doc.updated_at)}</time>
      </TableCell>
      <TableCell className="w-px text-right">
        {hasMenu ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${title}`}>
                <Ellipsis aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {openable ? (
                <DropdownMenuItem asChild>
                  <Link to="/app/notes/pdf/$docId" params={{ docId: doc.id }}>
                    <FileText aria-hidden /> Open
                  </Link>
                </DropdownMenuItem>
              ) : null}
              {onEdit ? (
                <DropdownMenuItem onSelect={() => onEdit(doc)}>
                  <Pencil aria-hidden /> Edit details
                </DropdownMenuItem>
              ) : null}
              {onMakeSearchable && needsOcr ? (
                <DropdownMenuItem onSelect={() => onMakeSearchable(doc)}>
                  <ScanText aria-hidden /> Make searchable
                </DropdownMenuItem>
              ) : null}
              {onExport && doc.status === 'ready' ? (
                <DropdownMenuItem onSelect={() => onExport(doc)}>
                  <FileDown aria-hidden /> Export with my marks
                </DropdownMenuItem>
              ) : null}
              {onDownload && doc.origin === 'upload' && openable ? (
                <DropdownMenuItem onSelect={() => onDownload(doc)}>
                  <Download aria-hidden /> Download original
                </DropdownMenuItem>
              ) : null}
              {onTrash ? (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => onTrash(doc)}>
                    <Trash2 aria-hidden /> {doc.status === 'reserved' ? 'Cancel upload' : 'Move to Trash'}
                  </DropdownMenuItem>
                </>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </TableCell>
    </TableRow>
  )
}
