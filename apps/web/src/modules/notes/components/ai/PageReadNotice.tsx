import { Alert, Button, LoaderCircle, Sparkles } from '@artha/design-system'

import type { PageQuality } from '../../lib/ai-copy'

interface PageReadNoticeProps {
  page: number
  quality: PageQuality
  /** "Improve this page" is on offer (low confidence, nothing better yet). */
  canImprove: boolean
  working: boolean
  /** The outcome of the last try on this page: what happened, in plain words. */
  message?: string
  onImprove: () => void
}

/** One line above the reader: how well this page was read, and "Improve this page" when AI can do better. */
export function PageReadNotice({ page, quality, canImprove, working, message, onImprove }: PageReadNoticeProps) {
  if (!working && !message && !canImprove && quality.tone !== 'ai') return null
  return (
    <Alert variant="info" data-slot="page-read-notice">
      <div className="flex flex-wrap items-center gap-3">
        <p className="flex min-w-0 flex-1 items-start gap-2" role="status">
          {working ? (
            <LoaderCircle aria-hidden className="mt-0.5 size-4 shrink-0 animate-spin" />
          ) : (
            <Sparkles aria-hidden className="mt-0.5 size-4 shrink-0" />
          )}
          <span>{working ? `AI is reading page ${page}. You can keep reading.` : (message ?? quality.text)}</span>
        </p>
        {canImprove && !working ? (
          <Button size="sm" className="min-h-11" onClick={onImprove}>
            Improve this page
          </Button>
        ) : null}
      </div>
    </Alert>
  )
}
