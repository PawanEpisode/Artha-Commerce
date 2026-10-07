import {
  Badge,
  Button,
  Card,
  Download,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Ellipsis,
  FileDown,
  FileText,
  Lock,
  Pencil,
  ProgressBar,
  ScanText,
  Tag,
  Trash2,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { isUnfiled, linkLabel } from '../../lib/chapter-link'
import { canOpenDocument, documentBadges, documentTitle, readPercent } from '../../lib/document-badges'
import type { DocumentSummary } from '../../lib/document-types'
import { formatBytes, pluralize } from '../../lib/format'
import { DocumentStatusBadge } from './DocumentStatusBadge'

export interface DocumentCardActions {
  onEdit?: (doc: DocumentSummary) => void
  onExport?: (doc: DocumentSummary) => void
  onDownload?: (doc: DocumentSummary) => void
  onTrash?: (doc: DocumentSummary) => void
  onMakeSearchable?: (doc: DocumentSummary) => void
}

interface DocumentCardProps extends DocumentCardActions {
  doc: DocumentSummary
  /** A smaller card for the aggregated views and Continue reading: no menu, tags or progress. */
  compact?: boolean
  /** The list came from this device while offline. */
  offlineCopy?: boolean
  /** Hide the "where it is filed" chip when the page already says it. */
  showLocation?: boolean
  /** Adds a "Continue on page N" link (the hub's Continue reading row). */
  resume?: boolean
  className?: string
}

const SHARE_PRIVATE = new Set(['coaching', 'institute_material'])

/** One PDF in the library: cover, a two line title, pages and size, status, reading progress, chapter and tags, and a menu. */
export function DocumentCard({
  doc,
  compact = false,
  offlineCopy,
  showLocation = true,
  resume = false,
  className,
  onEdit,
  onExport,
  onDownload,
  onTrash,
  onMakeSearchable,
}: DocumentCardProps) {
  const title = documentTitle(doc)
  const badges = documentBadges(doc, { offlineCopy })
  const percent = readPercent(doc)
  const openable = canOpenDocument(doc)
  const needsOcr =
    doc.status === 'ready' && doc.is_scanned === true && (doc.ocr_status === 'none' || doc.ocr_status === 'failed')
  const hasMenu = !compact && (onEdit || onExport || onDownload || onTrash)

  const heading = openable ? (
    <Link
      to="/app/notes/pdf/$docId"
      params={{ docId: doc.id }}
      title={title}
      className="underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-[3px] focus-visible:ring-ring/40"
    >
      {title}
    </Link>
  ) : (
    <span title={title}>{title}</span>
  )

  return (
    <Card
      data-slot="document-card"
      data-status={doc.status}
      className={`flex items-start gap-3 p-3 sm:p-4 ${className ?? ''}`}
    >
      <div
        aria-hidden
        className={`relative grid shrink-0 place-items-center overflow-hidden rounded-md border border-border bg-muted ${compact ? 'h-16 w-12' : 'h-24 w-[4.5rem]'}`}
      >
        {doc.cover_url ? (
          <img src={doc.cover_url} alt="" loading="lazy" className="size-full object-cover" />
        ) : (
          <FileText className="size-6 text-muted-foreground" />
        )}
        {doc.status === 'needs_password' ? (
          <span className="absolute right-0.5 bottom-0.5 grid size-5 place-items-center rounded-full bg-card shadow-soft">
            <Lock className="size-3" />
          </span>
        ) : null}
      </div>

      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-start gap-1">
          <h3 className="line-clamp-2 min-w-0 flex-1 font-display text-base leading-snug font-bold break-words sm:text-lg">
            {heading}
          </h3>
          {hasMenu ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="-mt-1 -mr-1 shrink-0"
                  aria-label={`Actions for ${title}`}
                >
                  <Ellipsis aria-hidden />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
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
        </div>

        <p className="text-xs text-muted-foreground">
          {doc.page_count ? pluralize(doc.page_count, 'page') : 'Pages not counted yet'} · {formatBytes(doc.bytes)}
        </p>

        <div className="flex flex-wrap items-center gap-1.5">
          {badges.map((badge) => (
            <DocumentStatusBadge key={badge.kind} badge={badge} />
          ))}
          {SHARE_PRIVATE.has(doc.source_kind) && !compact ? <Badge variant="outline">Private to you</Badge> : null}
        </div>

        {percent !== null && !compact ? (
          <div className="flex items-center gap-2">
            <ProgressBar value={percent} label={`Read ${percent}%`} className="max-w-40 flex-1" />
            <span className="text-xs text-muted-foreground tabular-nums">Read {percent}%</span>
          </div>
        ) : null}

        {!compact || showLocation ? (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            {showLocation && !isUnfiled(doc.link) ? <Badge variant="outline">{linkLabel(doc.link)}</Badge> : null}
            {doc.link.moved_or_removed ? <Badge variant="outline">Chapter moved or removed</Badge> : null}
            {!compact
              ? doc.tags.map((tag) => (
                  <Badge key={tag.id} variant="outline">
                    <Tag aria-hidden className="size-3" />
                    {tag.name}
                  </Badge>
                ))
              : null}
          </div>
        ) : null}

        {resume && openable && doc.last_page > 0 ? (
          <Link
            to="/app/notes/pdf/$docId"
            params={{ docId: doc.id }}
            search={{ page: doc.last_page }}
            className="inline-flex min-h-11 items-center text-sm font-semibold text-primary underline-offset-4 hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/40 focus-visible:outline-none"
          >
            Continue on page {doc.last_page}
          </Link>
        ) : null}

        {needsOcr && onMakeSearchable && !compact ? (
          <Button size="sm" variant="outline" onClick={() => onMakeSearchable(doc)}>
            <ScanText aria-hidden /> Make searchable
          </Button>
        ) : null}
      </div>
    </Card>
  )
}
