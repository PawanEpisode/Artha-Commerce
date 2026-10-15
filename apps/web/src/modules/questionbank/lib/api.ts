import { api, publicApi } from '~/lib/api'

import type {
  PlayableQuestion,
  QuestionCardData,
  QuestionFacets,
  QuestionListResponse,
  QuestionSearchParams,
  ReviewQuestion,
} from './types'

export async function getPublicQuestions(params: QuestionSearchParams = {}): Promise<QuestionListResponse> {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.subject) query.set('subject', params.subject)
  if (params.chapter) query.set('chapter', params.chapter)
  if (params.kind) query.set('kind', params.kind)
  if (params.difficulty) query.set('difficulty', String(params.difficulty))
  if (params.year) query.set('year', String(params.year))
  if (params.term) query.set('term', params.term)
  if (params.tag) query.set('tag', params.tag)
  if (params.cursor) query.set('cursor', params.cursor)
  if (params.limit) query.set('limit', String(params.limit))

  const qs = query.toString()
  const path = `/questionbank/public/questions/${qs ? `?${qs}` : ''}`
  try {
    return await api<QuestionListResponse>(path)
  } catch {
    const res = await publicApi<QuestionListResponse>(path)
    return res ?? { items: [] }
  }
}

export async function getPublicQuestion(id: string): Promise<QuestionCardData | null> {
  const path = `/questionbank/public/questions/${id}/`
  try {
    return await api<QuestionCardData>(path)
  } catch {
    return await publicApi<QuestionCardData>(path)
  }
}

export async function getPlayableQuestion(id: string): Promise<PlayableQuestion> {
  return await api<PlayableQuestion>(`/questionbank/questions/${id}/playable/`)
}

export async function getReviewQuestion(id: string): Promise<ReviewQuestion> {
  return await api<ReviewQuestion>(`/questionbank/questions/${id}/review/`)
}

export async function getQuestionFacets(): Promise<QuestionFacets> {
  const path = '/questionbank/public/facets/'
  try {
    return await api<QuestionFacets>(path)
  } catch {
    const res = await publicApi<QuestionFacets>(path)
    return res ?? { kinds: {}, difficulties: {}, years: {}, subjects: {} }
  }
}

export interface ReportQuestionPayload {
  reason:
    | 'wrong_answer'
    | 'typo'
    | 'unclear'
    | 'outdated_law'
    | 'wrong_chapter'
    | 'duplicate'
    | 'copyright'
    | 'offensive'
    | 'other'
  message?: string
}

export async function reportQuestion(
  id: string,
  payload: ReportQuestionPayload,
): Promise<{ id: string; status: string }> {
  return await api<{ id: string; status: string }>(`/questionbank/questions/${id}/report/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export interface CsvImportResult {
  total_rows: number
  imported_count: number
  errors: string[]
}

export async function importQuestionsCsv(csvText: string, autoPublish = false): Promise<CsvImportResult> {
  return await api<CsvImportResult>('/questionbank/editor/import-csv/', {
    method: 'POST',
    body: JSON.stringify({ csv_text: csvText, auto_publish: autoPublish }),
  })
}

export interface ReviewQueueItem {
  id: string
  question_id: string
  version_id: string
  kind: string
  status: string
  stem_head: string
  question_kind: string
  submitted_at: string | null
  sla_due_at: string | null
}

export async function getEditorReviewQueue(status = 'pending'): Promise<ReviewQueueItem[]> {
  const res = await api<{ items: ReviewQueueItem[] }>(`/questionbank/editor/review-queue/?status=${status}`)
  return res.items
}

export interface EditorReportItem {
  id: string
  question_id: string
  version_id: string
  kind: string
  message: string
  status: string
  stem_head: string
  created_at: string
}

export async function getEditorReports(status = 'open'): Promise<EditorReportItem[]> {
  const res = await api<{ items: EditorReportItem[] }>(`/questionbank/editor/reports/?status=${status}`)
  return res.items
}

export async function resolveEditorReport(
  reportId: string,
  payload: { status?: string; note?: string },
): Promise<{ report_id: string; status: string }> {
  return await api<{ report_id: string; status: string }>(`/questionbank/editor/reports/${reportId}/resolve/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
