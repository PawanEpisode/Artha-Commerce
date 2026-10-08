import { api } from '~/lib/api'

import type { AiConsent, AiOcrJob, AiOcrStarted, SummaryJob, WithdrawReport } from './ai-types'

const json = (body: unknown) => JSON.stringify(body)

/** Consent: read the text and the student's state, agree to a version, or take it back (never needs the flag). */
export const getAiConsent = () => api<AiConsent>('/notes/ai/consent/')
export const grantAiConsent = (version: string) =>
  api<AiConsent>('/notes/ai/consent/', { method: 'PUT', body: json({ version }) })
export const withdrawAiConsent = () => api<WithdrawReport>('/notes/ai/consent/withdraw/', { method: 'DELETE' })

/** Summary: ask (202 new job, 200 when the same inputs were summarised before), read, review, take back. */
export const requestSummary = (body: {
  client_id: string
  chapter_id: string
  include?: Array<'notes' | 'highlights'>
}) => api<SummaryJob>('/notes/ai/summary/', { method: 'POST', body: json(body) })
export const getSummary = (id: string) => api<SummaryJob>(`/notes/ai/summary/${id}/`)
export const latestSummary = (chapterId: string) =>
  api<{ job: SummaryJob | null }>(`/notes/ai/summary/?chapter_id=${encodeURIComponent(chapterId)}`)
export const acceptSummary = (id: string, body: { title?: string; body_md?: string }) =>
  api<{ job: SummaryJob; note: { id: string; title: string } }>(`/notes/ai/summary/${id}/accept/`, {
    method: 'POST',
    body: json(body),
  })
export const discardSummary = (id: string) =>
  api<SummaryJob>(`/notes/ai/summary/${id}/discard/`, { method: 'POST', body: json({}) })
export const cancelSummary = (id: string) =>
  api<SummaryJob>(`/notes/ai/summary/${id}/cancel/`, { method: 'POST', body: json({}) })

/** "Improve this page": the same `ocr/` endpoint with `mode: "ai"` (202 with the job, 200 when every page was skipped). */
export const requestAiOcr = (documentId: string, pages: string) =>
  api<AiOcrStarted>(`/notes/documents/${documentId}/ocr/`, { method: 'POST', body: json({ mode: 'ai', pages }) })
export const getAiOcr = (jobId: string) => api<AiOcrJob>(`/notes/ai/ocr/${jobId}/`)
export const cancelAiOcr = (jobId: string) =>
  api<AiOcrJob>(`/notes/ai/ocr/${jobId}/cancel/`, { method: 'POST', body: json({}) })
