import { Alert, Button, Dialog, DialogContent, DialogDescription, DialogTitle, Skeleton } from '@artha/design-system'

import type { UpdatePreview } from '../lib/schemas'
import { bannerTitle, KIND_LABEL, kindsIn, moreText, returningText } from '../lib/updates'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  preview: UpdatePreview | undefined
  loading: boolean
  error: string | null
  applying: boolean
  offline: boolean
  onApply: () => void
  onRetry: () => void
}

/** What an update would do, in words: the change log, the kinds of change with a few cards each, and what returns today. */
export function UpdateSheet({
  open,
  onOpenChange,
  preview,
  loading,
  error,
  applying,
  offline,
  onApply,
  onRetry,
}: Props) {
  const kinds = preview ? kindsIn(preview.counts) : []
  return (
    <Dialog open={open} onOpenChange={(next) => (applying ? undefined : onOpenChange(next))}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto">
        <DialogTitle>{preview ? bannerTitle(preview.counts.total ?? 0) : 'Update available'}</DialogTitle>
        <DialogDescription>
          {preview
            ? `From version ${preview.from_version_no} to version ${preview.to_version_no}.`
            : 'Checking what changed…'}
        </DialogDescription>
        {loading ? (
          <div aria-busy="true" className="space-y-2">
            <span className="sr-only" role="status">
              Loading the changes…
            </span>
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : null}
        {error ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              {error}
              <Button variant="outline" size="sm" onClick={onRetry}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : null}
        {preview ? (
          <div className="space-y-4">
            {preview.changelog_md ? (
              <p className="text-sm break-words whitespace-pre-line">{preview.changelog_md}</p>
            ) : null}
            {kinds.map((kind) => {
              const rows = preview.items[kind] ?? []
              return (
                <section key={kind} aria-label={KIND_LABEL[kind]} className="space-y-1.5">
                  <h3 className="text-sm font-semibold">
                    {KIND_LABEL[kind]} ({preview.counts[kind]})
                  </h3>
                  {rows.length > 0 ? (
                    <ul className="list-disc space-y-1 pl-5 text-sm break-words text-muted-foreground">
                      {rows.map((r) => (
                        <li key={r.item_id}>{r.label}</li>
                      ))}
                    </ul>
                  ) : null}
                  {moreText(preview, kind) ? (
                    <p className="text-xs text-muted-foreground">{moreText(preview, kind)}</p>
                  ) : null}
                </section>
              )
            })}
            {returningText(preview.returning_today) ? (
              <p className="text-sm">{returningText(preview.returning_today)}</p>
            ) : null}
            {offline ? <Alert variant="info">You are offline. Connect to apply this update.</Alert> : null}
          </div>
        ) : null}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" disabled={applying} onClick={() => onOpenChange(false)}>
            Not now
          </Button>
          <Button loading={applying} disabled={!preview || offline} onClick={onApply}>
            Apply update
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
