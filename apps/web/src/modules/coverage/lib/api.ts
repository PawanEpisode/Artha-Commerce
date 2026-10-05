import { api, ApiError } from '~/lib/api'

import type {
  CatchupResult,
  ChapterCoverage,
  ChapterState,
  Confidence,
  CoverageSettings,
  Due,
  ElectivesResult,
  Enrollment,
  EnrollmentWithSummary,
  EventType,
  Overview,
  SubjectCoverage,
} from './types'

const json = (body: unknown) => JSON.stringify(body)
const put = <T>(path: string, body: unknown) => api<T>(path, { method: 'PUT', body: json(body) })
const post = <T>(path: string, body: unknown) => api<T>(path, { method: 'POST', body: json(body) })

/** A fresh idempotency key per user action. The server ignores a repeated one, so retries never double count. */
export const newClientId = () => crypto.randomUUID()

/** 404 from the coverage endpoints means "no active enrolment yet": not an error for the UI. */
export const isNoEnrollment = (error: unknown) => error instanceof ApiError && error.status === 404

/**
 * 403 `feature_disabled`: the server-side `syllabus_coverage` flag is off for this user. The screens treat it exactly
 * like the web flag being off ("not available yet"), so the two switches never disagree on what the student sees.
 */
export function isFeatureDisabled(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 403) return false
  const code = (error.body as { error?: { code?: unknown } } | undefined)?.error?.code
  return code === 'feature_disabled'
}

export const listEnrollments = () => api<{ results: Enrollment[] }>('/coverage/enrollments/').then((r) => r.results)
export const createEnrollment = (input: {
  scheme: string
  target_term?: string | null
  exam_date?: string | null
  daily_hours?: number | null
  /** Elective slot key -> chosen subject id. */
  electives?: Record<string, string>
}) => post<Enrollment>('/coverage/enrollments/', input)
export const updateEnrollment = (
  id: string,
  patch: {
    target_term?: string | null
    exam_date?: string | null
    daily_hours?: number | null
    archive?: boolean
    scheme?: string
  },
) => api<EnrollmentWithSummary>(`/coverage/enrollments/${id}/`, { method: 'PATCH', body: json(patch) })

/** Sets (or, with null, clears) the elective of each slot named. The response carries the re-counted overview. */
export const setElectives = (enrollmentId: string, choices: Record<string, string | null>) =>
  put<ElectivesResult>(`/coverage/enrollments/${enrollmentId}/electives/`, { choices })

export const getOverview = () => api<Overview>('/coverage/overview/')
export const getSubject = (id: string) => api<SubjectCoverage>(`/coverage/subjects/${id}/`)
export const getChapter = (id: string) => api<ChapterCoverage>(`/coverage/chapters/${id}/`)
export const getDue = () => api<Due>('/coverage/due/')

/** Path and body of each idempotent write, shared by the live call and the offline queue that replays it. */
export const topicTickRequest = (topicId: string, done: boolean, clientId: string) => ({
  method: 'PUT' as const,
  path: `/coverage/topics/${topicId}/`,
  body: { done, client_id: clientId },
})
export const chapterTickRequest = (chapterId: string, done: boolean, clientId: string) => ({
  method: 'PUT' as const,
  path: `/coverage/chapters/${chapterId}/read/`,
  body: { done, client_id: clientId },
})
export const eventRequest = (input: {
  chapter_id: string
  type: EventType
  value?: number | null
  client_id: string
}) => ({
  method: 'POST' as const,
  path: '/coverage/events/',
  body: input as Record<string, unknown>,
})

export const tickTopic = (topicId: string, done: boolean, clientId: string) => {
  const r = topicTickRequest(topicId, done, clientId)
  return put<ChapterState>(r.path, r.body)
}
export const tickChapter = (chapterId: string, done: boolean, clientId: string) => {
  const r = chapterTickRequest(chapterId, done, clientId)
  return put<ChapterState>(r.path, r.body)
}
export const logEvent = (input: { chapter_id: string; type: EventType; value?: number | null; client_id: string }) => {
  const r = eventRequest(input)
  return post<ChapterState>(r.path, r.body)
}
export const setConfidence = (chapterId: string, confidence: Confidence | null) =>
  put<ChapterState>(`/coverage/chapters/${chapterId}/confidence/`, { confidence })
export const setChapterExclusion = (chapterId: string, excluded: boolean) =>
  put<ChapterState>(`/coverage/chapters/${chapterId}/exclusion/`, { excluded })
export const setSubjectExclusion = (subjectId: string, excluded: boolean) =>
  put<{ changed: number; overview: Overview }>(`/coverage/subjects/${subjectId}/exclusion/`, { excluded })
export const catchup = (input: { chapter_ids: string[]; also_revised: boolean; client_id: string }) =>
  post<CatchupResult>('/coverage/catchup/', input)

export const getSettings = () => api<CoverageSettings>('/coverage/settings/')
export const saveSettings = (settings: CoverageSettings) => put<CoverageSettings>('/coverage/settings/', settings)
export const resetSettings = () => api<CoverageSettings>('/coverage/settings/', { method: 'DELETE' })

export const exportCoverage = () => api<Record<string, unknown>>('/coverage/export/')
export const deleteCoverage = () => api<void>('/coverage/', { method: 'DELETE' })
