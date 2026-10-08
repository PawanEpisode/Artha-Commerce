import { Button, LoaderCircle, RefreshCw } from '@artha/design-system'

interface ReplaceSectionProps {
  /** Where the marks of the old edition are, in words. Null when this document is not a newer edition. */
  statusText: string | null
  working: boolean
  openCount: number
  canReplace: boolean
  online: boolean
  onReview: () => void
  onReplace: () => void
}

/** In the document details: the state of a newer edition's marks, and "Replace with a newer edition". */
export function ReplaceSection({
  statusText,
  working,
  openCount,
  canReplace,
  online,
  onReview,
  onReplace,
}: ReplaceSectionProps) {
  if (!statusText && !canReplace) return null
  return (
    <div className="grid gap-2" data-slot="replace-section">
      <span className="text-sm font-semibold">Editions</span>
      {statusText ? (
        <p className="flex items-start gap-2 text-sm" role="status">
          {working ? <LoaderCircle aria-hidden className="mt-0.5 size-4 shrink-0 animate-spin" /> : null}
          <span>{statusText}</span>
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {openCount > 0 ? (
          <Button variant="outline" className="min-h-11" onClick={onReview}>
            Review {openCount} {openCount === 1 ? 'mark' : 'marks'}
          </Button>
        ) : null}
        {canReplace ? (
          <Button variant="outline" className="min-h-11" onClick={onReplace} disabled={!online}>
            <RefreshCw aria-hidden /> Replace with a newer edition
          </Button>
        ) : null}
      </div>
      {canReplace ? (
        <p className="text-sm text-muted-foreground">
          Your marks move to the new file where the words match. This edition stays in your library.
        </p>
      ) : null}
    </div>
  )
}
