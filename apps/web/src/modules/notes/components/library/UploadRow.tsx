import {
  Button,
  CircleAlert,
  CircleCheck,
  FileText,
  LoaderCircle,
  Lock,
  ProgressBar,
  ScanText,
  X,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { formatBytes } from '../../lib/format'
import { type UploadItem, uploadPercent } from '../../lib/upload-manager'

export interface UploadRowActions {
  onCancel: (id: string) => void
  onRetry: (id: string) => void
  onDismiss: (id: string) => void
  onKeepBoth: (id: string) => void
  /** "Open it" for a duplicate: goes to the copy the student already had (the new one is discarded). */
  onOpenExisting: (item: UploadItem) => void
  /** A quota failure: opens the quota sheet with what the server said. */
  onManageStorage: (item: UploadItem) => void
}

const CANCELLABLE = new Set(['reserving', 'uploading', 'completing'])

/**
 * One upload, wherever it is shown (the chip in the app layout, the top of the library): what it is doing in words,
 * a progress bar with bytes while the file moves, and the actions that make sense for the state. Never a dead end.
 */
export function UploadRow({ item, compact, ...actions }: { item: UploadItem; compact?: boolean } & UploadRowActions) {
  const percent = uploadPercent(item)
  const failure = item.failure
  const isFailed = item.phase === 'failed'
  return (
    <div
      data-slot="upload-row"
      data-phase={item.phase}
      className="flex items-start gap-3 rounded-xl border border-border bg-card p-3 text-sm shadow-soft"
    >
      <span aria-hidden className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-muted">
        {isFailed ? (
          <CircleAlert className="size-4 text-error-fg" />
        ) : item.phase === 'ready' ? (
          <CircleCheck className="size-4 text-success-fg" />
        ) : item.phase === 'duplicate' ? (
          <FileText className="size-4" />
        ) : (
          <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" />
        )}
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className="truncate font-semibold" title={item.fileName}>
          {item.fileName}
        </p>

        {item.phase === 'reserving' ? <p className="text-muted-foreground">Reserving space…</p> : null}
        {item.phase === 'uploading' || item.phase === 'completing' ? (
          <>
            <ProgressBar value={percent ?? 0} label={`Uploading ${item.fileName}`} />
            <p className="text-muted-foreground tabular-nums">
              {item.phase === 'completing'
                ? 'Finishing…'
                : `${percent}% · ${formatBytes(item.loaded)} of ${formatBytes(item.bytes)}`}
            </p>
          </>
        ) : null}
        {item.phase === 'processing' ? (
          <p className="text-muted-foreground">Checking your PDF. You can keep working.</p>
        ) : null}
        {item.phase === 'ready' ? (
          <p className="text-foreground">
            {item.encrypted ? (
              <span className="inline-flex items-center gap-1.5">
                <Lock aria-hidden className="size-3.5" /> Added. Locked: opens with your password.
              </span>
            ) : item.scanned ? (
              <span className="inline-flex items-center gap-1.5">
                <ScanText aria-hidden className="size-3.5" /> Added. Scanned: search needs OCR.
              </span>
            ) : (
              'Added to your library.'
            )}
          </p>
        ) : null}
        {item.phase === 'duplicate' ? <p className="text-foreground">You already have this file.</p> : null}
        {isFailed && failure ? (
          <p className="text-foreground">
            {failure.message}
            {failure.requestId ? (
              <span className="block text-xs text-muted-foreground">Request {failure.requestId}</span>
            ) : null}
            {failure.reason === 'too_large' || failure.reason === 'too_many_pages' ? (
              <span className="block text-muted-foreground">Split the PDF or compress it, then choose it again.</span>
            ) : null}
          </p>
        ) : null}

        {!compact || isFailed || item.phase === 'duplicate' || item.phase === 'ready' ? (
          <div className="flex flex-wrap gap-2 pt-0.5">
            {item.phase === 'ready' && item.documentId ? (
              <Button size="sm" asChild>
                <Link to="/app/notes/pdf/$docId" params={{ docId: item.documentId }}>
                  Open
                </Link>
              </Button>
            ) : null}
            {item.phase === 'duplicate' ? (
              <>
                <Button size="sm" onClick={() => actions.onOpenExisting(item)}>
                  Open it
                </Button>
                <Button size="sm" variant="outline" onClick={() => actions.onKeepBoth(item.id)}>
                  Keep both
                </Button>
              </>
            ) : null}
            {isFailed && failure?.retryable ? (
              <Button size="sm" onClick={() => actions.onRetry(item.id)}>
                Retry
              </Button>
            ) : null}
            {isFailed && failure?.reason === 'quota' ? (
              <Button size="sm" onClick={() => actions.onManageStorage(item)}>
                Manage storage
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
      {CANCELLABLE.has(item.phase) ? (
        <Button
          variant="ghost"
          size="sm"
          className="shrink-0"
          aria-label={`Cancel uploading ${item.fileName}`}
          onClick={() => actions.onCancel(item.id)}
        >
          Cancel
        </Button>
      ) : item.phase === 'duplicate' ? null : (
        <Button
          variant="ghost"
          size="icon"
          className="-mt-1 -mr-1 shrink-0"
          aria-label={`Dismiss ${item.fileName}`}
          onClick={() => actions.onDismiss(item.id)}
        >
          <X aria-hidden />
        </Button>
      )}
    </div>
  )
}
