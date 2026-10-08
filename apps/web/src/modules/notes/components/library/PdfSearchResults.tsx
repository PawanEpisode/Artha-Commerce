import { Alert, Button, Card, FileText, Highlighter, Lock, ScanText } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { linkLabel } from '../../lib/chapter-link'
import { pluralize } from '../../lib/format'
import type { ColorLegend, MarkSearchHit } from '../../lib/library-types'
import { markOpenedFrom } from '../../lib/opened-from'
import { type NotSearchable, type PdfGroup } from '../../lib/search-groups'
import { splitHighlight } from '../../lib/search-query'
import { ColorDot } from './HighlightRow'

function Marked({ text, query }: { text: string; query: string }) {
  return (
    <>
      {splitHighlight(text, query).map((piece, index) =>
        piece.match ? (
          <mark key={index} className="rounded-sm bg-highlight/30 px-0.5 text-foreground">
            {piece.text}
          </mark>
        ) : (
          <span key={index}>{piece.text}</span>
        ),
      )}
    </>
  )
}

interface PdfResultGroupsProps {
  groups: readonly PdfGroup[]
  query: string
  onOpen?: () => void
}

/** PDF hits grouped by document: the title, then up to five pages with the matching words marked and "Open page N". */
export function PdfResultGroups({ groups, query, onOpen }: PdfResultGroupsProps) {
  return (
    <ul aria-label="PDF results" className="space-y-3">
      {groups.map((group) => (
        <li key={group.documentId}>
          <Card className="space-y-3 p-4">
            <h3 className="flex items-start gap-2 font-display text-lg leading-snug font-bold break-words">
              <FileText aria-hidden className="mt-1 size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0">{group.title.trim() || 'Untitled PDF'}</span>
            </h3>
            <ul className="space-y-3">
              {group.hits.map((hit) => (
                <li key={hit.page} className="space-y-1">
                  <p className="line-clamp-3 text-sm break-words text-muted-foreground">
                    <Marked text={hit.snippet} query={query} />
                  </p>
                  <Link
                    to="/app/notes/pdf/$docId"
                    params={{ docId: group.documentId }}
                    search={{ page: hit.page, q: query }}
                    onClick={() => {
                      markOpenedFrom('search')
                      onOpen?.()
                    }}
                    aria-label={`Open page ${hit.page} of ${group.title.trim() || 'this PDF'}`}
                    className="inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
                  >
                    Open page {hit.page}
                  </Link>
                </li>
              ))}
            </ul>
            {group.more > 0 ? (
              <p className="text-xs text-muted-foreground">
                and {pluralize(group.more, 'more page')} in this document. Open it and search inside.
              </p>
            ) : null}
          </Card>
        </li>
      ))}
    </ul>
  )
}

interface MarkResultsProps {
  hits: readonly MarkSearchHit[]
  query: string
  legend?: ColorLegend
  onOpen?: () => void
}

/** Highlights and comments that match: the text, the colour NAME, the document and page. Opens at the mark. */
export function MarkResults({ hits, query, legend, onOpen }: MarkResultsProps) {
  return (
    <ul aria-label="Highlight results" className="space-y-3">
      {hits.map((hit) => (
        <li key={hit.annotation_id}>
          <Card className="space-y-1 p-4">
            <p className="flex items-start gap-2 text-base leading-snug break-words">
              <Highlighter aria-hidden className="mt-1 size-4 shrink-0 text-muted-foreground" />
              <Link
                to="/app/notes/pdf/$docId"
                params={{ docId: hit.document_id }}
                search={{ page: hit.page, ann: hit.annotation_id }}
                onClick={() => {
                  markOpenedFrom('search')
                  onOpen?.()
                }}
                className="min-w-0 underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-[3px] focus-visible:ring-ring/40"
              >
                <Marked text={hit.snippet} query={query} />
              </Link>
            </p>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
              {hit.color ? (
                <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
                  <ColorDot color={hit.color} />
                  {legend?.[hit.color as keyof ColorLegend] ?? 'Colour'}
                </span>
              ) : null}
              <span className="min-w-0 break-words">
                {hit.document_title} · page {hit.page}
              </span>
              <span>{linkLabel(hit.link)}</span>
            </p>
          </Card>
        </li>
      ))}
    </ul>
  )
}

interface PdfSearchNoticesProps {
  indexing: string | null
  notSearchable: NotSearchable | null
  /** Titles by document id. */
  titles: ReadonlyMap<string, string>
  documents: ReadonlyArray<{ document_id: string; reason: string }>
  onMakeSearchable: (documentId: string) => void
  busyId?: string | null
}

/** Why some PDFs are missing from the results: still indexing, locked, or scanned with a one tap fix. */
export function PdfSearchNotices({
  indexing,
  notSearchable,
  titles,
  documents,
  onMakeSearchable,
  busyId,
}: PdfSearchNoticesProps) {
  if (!indexing && !notSearchable) return null
  const rows = documents.filter((d) => d.reason === 'scanned' || d.reason === 'locked').slice(0, 5)
  return (
    <div className="space-y-2">
      {indexing ? (
        <Alert variant="info">
          <span>{indexing} Their pages will appear in a moment.</span>
        </Alert>
      ) : null}
      {notSearchable ? (
        <Alert variant="info">
          <div className="space-y-2">
            <p>{notSearchable.text}</p>
            <ul className="space-y-1">
              {rows.map((d) => {
                const title = titles.get(d.document_id) ?? 'A PDF'
                return (
                  <li key={d.document_id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="min-w-0 flex-1 break-words">
                      {title} {d.reason === 'locked' ? '(locked, open it to enter the password)' : '(scanned pages)'}
                    </span>
                    {d.reason === 'scanned' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={`Make searchable: ${title}`}
                        disabled={busyId === d.document_id}
                        onClick={() => onMakeSearchable(d.document_id)}
                      >
                        <ScanText aria-hidden /> Make searchable
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" asChild>
                        <Link to="/app/notes/pdf/$docId" params={{ docId: d.document_id }} aria-label={`Open ${title}`}>
                          <Lock aria-hidden /> Open
                        </Link>
                      </Button>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        </Alert>
      ) : null}
    </div>
  )
}
