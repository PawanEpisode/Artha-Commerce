import { Alert, Button, ProgressBar, ScanText } from '@artha/design-system'

import type { OcrStatus } from '../../lib/document-types'

export interface ScannedBannerProps {
  status: OcrStatus
  pagesDone: number
  pagesTotal: number
  /** Starts OCR (the library slice wires it, with the quota sheet). Without it the banner explains but offers nothing. */
  onMakeSearchable?: () => void
  onDismiss: () => void
  busy?: boolean
}

/**
 * Shown on a scanned PDF until OCR is done or the student says "Not now" (PRD 7.3). The area highlight, pen, pin and text
 * box keep working; OCR adds search and text selection. With OCR running it turns into a progress line.
 */
export function ScannedBanner({
  status,
  pagesDone,
  pagesTotal,
  onMakeSearchable,
  onDismiss,
  busy,
}: ScannedBannerProps) {
  if (status === 'done') return null
  const running = status === 'pending' || status === 'running'
  const partial = status === 'partial' || (running && pagesDone > 0)
  return (
    <Alert variant="info" data-slot="scanned-banner">
      <div className="flex flex-col gap-2">
        <p className="flex items-start gap-2">
          <ScanText className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {running
              ? `Making this PDF searchable: ${pagesDone} of ${pagesTotal || '…'} pages.`
              : status === 'failed'
                ? 'We could not finish making this PDF searchable.'
                : 'Scanned pages. Search and text selection need OCR.'}
            {partial ? ' Pages that are done can already be selected and searched.' : ''}
          </span>
        </p>
        {running && pagesTotal > 0 ? (
          <ProgressBar value={Math.round((pagesDone / pagesTotal) * 100)} label="OCR progress" />
        ) : null}
        <div className="flex flex-wrap gap-2">
          {!running && onMakeSearchable ? (
            <Button size="sm" className="min-h-11" onClick={onMakeSearchable} loading={busy}>
              {status === 'failed' ? 'Try again' : 'Make searchable'}
            </Button>
          ) : null}
          <Button size="sm" variant="ghost" className="min-h-11" onClick={onDismiss}>
            {running ? 'Hide' : 'Not now'}
          </Button>
        </div>
      </div>
    </Alert>
  )
}
