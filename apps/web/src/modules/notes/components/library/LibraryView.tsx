import { Alert, Button, CloudOff, EmptyState, FileText, Plus, Skeleton, UsageBar } from '@artha/design-system'
import type { ReactNode } from 'react'

import type { DocumentSummary } from '../../lib/document-types'
import { formatBytes, pluralize } from '../../lib/format'
import type { Usage } from '../../lib/types'
import { MIB, type UploadLimits } from '../../lib/upload-check'
import { LibraryEmpty } from './LibraryEmpty'

interface LibraryViewProps {
  state: 'loading' | 'error' | 'ready'
  items: readonly DocumentSummary[]
  /** Any filter or search text is on, so an empty list means "nothing matches", not "no PDFs yet". */
  filtered: boolean
  usage?: Usage
  limits: UploadLimits
  online: boolean
  /** The error's request id, shown beside Retry when the API sent one. */
  requestId?: string
  filters: ReactNode
  /** Upload rows (progress, failures, duplicates) shown above the list. */
  uploads: ReactNode
  hasUploads: boolean
  hasMore: boolean
  loadingMore: boolean
  onLoadMore: () => void
  onRetry: () => void
  onUpload: () => void
  onFiles: (files: File[]) => void
  onClearFilters: () => void
  renderCard: (doc: DocumentSummary) => ReactNode
}

const mb = (bytes: number) => Math.round(bytes / MIB)

/**
 * The PDF library screen (PRD 7.2, 7.3): usage, Upload, filters, upload rows and the cards, with every state designed:
 * loading skeletons, first-time empty, no match, error that keeps the last list dimmed, offline and long lists by cursor.
 */
export function LibraryView(props: LibraryViewProps) {
  const { state, items, filtered, usage, limits, online, requestId, hasMore, loadingMore } = props
  const showEmptyFirstTime = state === 'ready' && items.length === 0 && !filtered && !props.hasUploads
  return (
    <>
      <header className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl font-extrabold">Library</h1>
            <p className="text-muted-foreground">Your PDFs, ready to read and mark.</p>
          </div>
          <div className="flex flex-col items-start gap-1 sm:items-end">
            <Button
              variant="cta"
              onClick={props.onUpload}
              disabled={!online}
              aria-describedby={!online ? 'library-offline-reason' : undefined}
            >
              <Plus aria-hidden /> Upload PDF
            </Button>
            {!online ? (
              <p id="library-offline-reason" className="text-sm text-muted-foreground">
                You are offline. Upload needs a connection.
              </p>
            ) : null}
          </div>
        </div>
        {usage ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <UsageBar
              label="PDF storage"
              used={mb(usage.used.storage_bytes)}
              limit={usage.limits.max_storage_mb}
              unit="MB"
              fullText="Storage full"
            />
            <UsageBar
              label="PDFs"
              used={usage.used.documents ?? 0}
              limit={usage.limits.max_documents ?? limits.maxDocuments}
              fullText="PDF limit reached"
            />
          </div>
        ) : state === 'loading' ? (
          <Skeleton className="h-12 w-full" />
        ) : null}
      </header>

      {!online ? (
        <Alert variant="info">
          <span className="flex items-center gap-2">
            <CloudOff aria-hidden className="size-4 shrink-0" />
            Offline: showing the PDFs this device already loaded. Opening a PDF needs a connection.
          </span>
        </Alert>
      ) : null}

      {props.uploads}

      {showEmptyFirstTime ? (
        <LibraryEmpty limits={limits} online={online} onFiles={props.onFiles} />
      ) : (
        <>
          {props.filters}
          {state === 'loading' ? (
            <div aria-busy="true" className="space-y-3">
              <span role="status" className="sr-only">
                Loading your PDFs…
              </span>
              {[0, 1, 2].map((i) => (
                <div key={i} className="flex gap-3 rounded-xl border border-border bg-card p-4">
                  <Skeleton className="h-24 w-[4.5rem] shrink-0" />
                  <div className="min-w-0 flex-1 space-y-2">
                    <Skeleton className="h-5 w-3/4" />
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-6 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {state === 'error' ? (
                <Alert variant="error">
                  <span className="flex flex-wrap items-center gap-3">
                    <span>We could not load your PDFs.{items.length > 0 ? ' This is the last list we had.' : ''}</span>
                    {requestId ? <span className="text-xs text-muted-foreground">Request {requestId}</span> : null}
                    <Button size="sm" variant="outline" onClick={props.onRetry}>
                      Try again
                    </Button>
                  </span>
                </Alert>
              ) : null}
              {items.length === 0 && state === 'ready' ? (
                <EmptyState
                  icon={<FileText aria-hidden />}
                  title="No PDFs match"
                  description="Try different words, or remove a filter."
                  action={
                    <Button variant="outline" onClick={props.onClearFilters}>
                      Clear all filters
                    </Button>
                  }
                />
              ) : (
                <ul aria-label="Your PDFs" className={`space-y-3 ${state === 'error' ? 'opacity-60' : ''}`}>
                  {items.map((doc) => (
                    <li key={doc.id}>{props.renderCard(doc)}</li>
                  ))}
                </ul>
              )}
              {items.length > 0 ? (
                <p className="text-sm text-muted-foreground" role="status">
                  Showing {pluralize(items.length, 'PDF')}
                  {hasMore ? ' so far' : ''}
                  {usage ? `, ${formatBytes(usage.used.storage_bytes)} used in all` : ''}.
                </p>
              ) : null}
              {hasMore ? (
                <Button variant="outline" onClick={props.onLoadMore} disabled={loadingMore}>
                  {loadingMore ? 'Loading…' : 'Load more'}
                </Button>
              ) : null}
            </div>
          )}
        </>
      )}
    </>
  )
}
