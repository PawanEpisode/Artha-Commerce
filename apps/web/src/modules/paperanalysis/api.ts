import { api } from '~/lib/api'

import type {
  AskedSummaryBadge,
  ChapterHistorySitting,
  ChapterStatsRow,
  EditorialPaperDetail,
  PaperAnalysisSettings,
  PatternsResponse,
  Plan,
  PlanPreview,
  PriorityView,
  SubjectStatus,
} from './types'

const BASE = '/paperanalysis'

const get = <T>(path: string) => api<T>(path)
const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined })
const patch = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined })
const del = <T>(path: string) => api<T>(path, { method: 'DELETE' })

export async function fetchSubjectStatuses(enrollmentId?: string): Promise<{ subjects: SubjectStatus[] }> {
  const query = enrollmentId ? `?enrollment_id=${enrollmentId}` : ''
  return get<{ subjects: SubjectStatus[] }>(`${BASE}/subjects/${query}`)
}

export async function fetchSubjectStats(
  subjectKey: string,
  options?: { window?: number },
): Promise<{ subject_key: string; window: number; chapters: ChapterStatsRow[] }> {
  const query = options?.window ? `?window=${options.window}` : ''
  return get<{ subject_key: string; window: number; chapters: ChapterStatsRow[] }>(
    `${BASE}/subjects/${subjectKey}/analysis/${query}`,
  )
}

export async function fetchSubjectPatterns(
  subjectKey: string,
  options?: { window?: number },
): Promise<PatternsResponse> {
  const query = options?.window ? `?window=${options.window}` : ''
  return get<PatternsResponse>(`${BASE}/subjects/${subjectKey}/patterns/${query}`)
}

export async function fetchChapterHistory(
  chapterKey: string,
  options?: { window?: number },
): Promise<{ chapter_key: string; history: ChapterHistorySitting[] }> {
  const query = options?.window ? `?window=${options.window}` : ''
  return get<{ chapter_key: string; history: ChapterHistorySitting[] }>(
    `${BASE}/chapters/${chapterKey}/history/${query}`,
  )
}

export async function fetchRecommendations(options?: {
  subjectKey?: string
  enrollmentId?: string
  forceRefresh?: boolean
}): Promise<PriorityView> {
  const params = new URLSearchParams()
  if (options?.subjectKey) params.set('subject_key', options.subjectKey)
  if (options?.enrollmentId) params.set('enrollment_id', options.enrollmentId)
  if (options?.forceRefresh) params.set('refresh', '1')
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<PriorityView>(`${BASE}/recommendations/${qs}`)
}

export async function previewPlan(payload: {
  days: number
  hours_per_day: number
  subject_keys?: string[]
  balance_subjects?: boolean
}): Promise<PlanPreview> {
  return post<PlanPreview>(`${BASE}/plan/preview/`, payload)
}

export async function adoptPlan(payload: {
  client_id: string
  days: number
  hours_per_day: number
  subject_keys?: string[]
  balance_subjects?: boolean
  start_date?: string
}): Promise<Plan> {
  return post<Plan>(`${BASE}/plan/adopt/`, payload)
}

export async function fetchActivePlan(): Promise<{ plan: Plan | null }> {
  return get<{ plan: Plan | null }>(`${BASE}/plan/active/`)
}

export async function replanActivePlan(payload: { days_remaining: number; hours_per_day: number }): Promise<Plan> {
  return post<Plan>(`${BASE}/plan/replan/`, payload)
}

export async function updatePlanItem(
  itemId: string,
  payload: { state: string },
): Promise<{ id: string; state: string }> {
  return patch<{ id: string; state: string }>(`${BASE}/plan/items/${itemId}/`, payload)
}

export async function endActivePlan(): Promise<{ status: string }> {
  return del<{ status: string }>(`${BASE}/plan/active/`)
}

export async function fetchSettings(): Promise<PaperAnalysisSettings> {
  return get<PaperAnalysisSettings>(`${BASE}/settings/`)
}

export async function updateSettings(payload: Partial<PaperAnalysisSettings>): Promise<PaperAnalysisSettings> {
  return patch<PaperAnalysisSettings>(`${BASE}/settings/`, payload)
}

export async function fetchAskedSummary(questionIds: string[]): Promise<Record<string, AskedSummaryBadge | null>> {
  if (questionIds.length === 0) return {}
  const qs = `?ids=${questionIds.join(',')}`
  const res = await get<{ results: Record<string, AskedSummaryBadge | null> }>(`${BASE}/asked/${qs}`)
  return res.results
}

// Editorial API
export async function fetchEditorialPapers(params?: Record<string, string>): Promise<{ papers: unknown[] }> {
  const query = params ? `?${new URLSearchParams(params).toString()}` : ''
  return get<{ papers: unknown[] }>(`${BASE}/papers/${query}`)
}

export async function fetchEditorialPaperDetail(paperId: string): Promise<EditorialPaperDetail> {
  return get<EditorialPaperDetail>(`${BASE}/papers/${paperId}/`)
}

export async function createEditorialPaper(payload: {
  subject_id: string
  term_code: string
  paper_kind: string
  total_marks: number
  series?: string
}): Promise<{ id: string; title: string }> {
  return post<{ id: string; title: string }>(`${BASE}/papers/`, payload)
}

export async function importSkeletonCsv(
  paperId: string,
  csvContent: string,
  dryRun = false,
): Promise<{ questions_created: number; dry_run: boolean; warnings: string[] }> {
  return post<{ questions_created: number; dry_run: boolean; warnings: string[] }>(
    `${BASE}/papers/${paperId}/import/`,
    { csv_content: csvContent, dry_run: dryRun },
  )
}

export async function setQuestionAllocations(
  questionId: string,
  allocations: { chapter_id: string; marks: number; topic_id?: string; rationale?: string }[],
  rev: number,
): Promise<unknown> {
  return post(`${BASE}/questions/${questionId}/allocations/`, { allocations, rev })
}

export async function confirmQuestion(questionId: string, rev: number): Promise<unknown> {
  return post(`${BASE}/questions/${questionId}/confirm/`, { rev })
}

export async function publishPaper(paperId: string): Promise<{ id: string; status: string }> {
  return post<{ id: string; status: string }>(`${BASE}/papers/${paperId}/publish/`, {})
}

export async function unpublishPaper(paperId: string, reason = ''): Promise<{ id: string; status: string }> {
  return post<{ id: string; status: string }>(`${BASE}/papers/${paperId}/unpublish/`, { reason })
}

export async function decideQa(
  questionId: string,
  decision: 'accepted' | 'rejected' | 'escalated',
  note = '',
): Promise<unknown> {
  return post(`${BASE}/questions/${questionId}/qa/`, { qa_state: decision, note })
}
