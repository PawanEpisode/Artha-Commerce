/** Shapes of the R3 AI endpoints (`docs/F-03-API-CONTRACT.md`, release R3). */

export interface AiConsentText {
  version: string
  title: string
  points: Array<{ heading: string; text: string }>
  checkbox: string
}

export interface AiConsent {
  text: AiConsentText
  consented: boolean
  version: string | null
  consented_at: string | null
  withdrawn_at: string | null
  /** False while the owner has not switched AI on for this deployment: the web shows "not available yet". */
  available: boolean
}

export type SummaryStatus =
  'queued' | 'running' | 'ready' | 'accepted' | 'discarded' | 'expired' | 'failed' | 'cancelled' | 'budget_blocked'

export interface SummarySource {
  n: number
  kind: 'note' | 'highlight'
  id: string
  page: number | null
  document_id: string | null
  label: string
}

export interface SummaryDraft {
  title: string
  body_md: string
  sources: SummarySource[]
  dropped: number
}

export type SummaryErrorCode = 'budget' | 'model_error' | 'blocked' | 'too_little' | 'consent_withdrawn' | 'unavailable'

export interface SummaryJob {
  id: string
  kind: 'exam_summary'
  status: SummaryStatus
  chapter: {
    chapter_id: string | null
    level_id: string | null
    subject_key: string | null
    chapter_key: string | null
  }
  item_count: number
  estimate_seconds: number
  /** True when an earlier job with the same inputs was returned: nothing was charged. */
  cached: boolean
  error_code: SummaryErrorCode | null
  charged: boolean
  created_at: string
  finished_at: string | null
  expires_at: string | null
  draft: SummaryDraft | null
  result_note_id: string | null
}

export interface WithdrawReport {
  drafts_deleted: number
  requests_cancelled: number
  consent: AiConsent
}

export interface NotEnoughDetails {
  items: number
  chars: number
  min_items: number
  min_chars: number
}

export const isSummaryActive = (status: SummaryStatus) => status === 'queued' || status === 'running'

export type PageLegibility = 'clear' | 'partial'

/** An AI read of some pages (`POST documents/{id}/ocr/ {mode: "ai"}`). Never carries page text: that is read from the document. */
export interface AiOcrJob {
  id: string
  kind: 'ocr_page_ai'
  status: SummaryStatus
  document_id: string | null
  pages: number[]
  done: Record<string, PageLegibility>
  failed: Record<string, string>
  refunded_pages: number[]
  charged_pages: number
  estimate_seconds: number
  error_code: SummaryErrorCode | null
  created_at: string
  finished_at: string | null
}

export interface AiOcrStarted {
  mode: 'ai'
  job: AiOcrJob | null
  charged_pages: number
  skipped: { already_read: number[]; has_text: number[]; in_progress: number[] }
  estimate_seconds: number
}
