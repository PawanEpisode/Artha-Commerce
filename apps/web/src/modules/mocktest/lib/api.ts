import { api } from '~/lib/api'

import type {
  AttemptResult,
  AttemptReview,
  AttemptState,
  ClockSyncResponse,
  MockPaperCard,
  MockTestSettings,
  PaperDetail,
  SeriesCard,
} from './types'

export async function fetchPapers(params?: {
  subject?: string
  kind?: string
  source?: string
  series_id?: string
  status?: string
}): Promise<{ papers: MockPaperCard[] }> {
  const q = new URLSearchParams()
  if (params?.subject) q.set('subject', params.subject)
  if (params?.kind) q.set('kind', params.kind)
  if (params?.source) q.set('source', params.source)
  if (params?.series_id) q.set('series_id', params.series_id)
  if (params?.status) q.set('status', params.status)

  const qs = q.toString()
  const res = await api<MockPaperCard[] | { papers: MockPaperCard[] }>(`/mocktest/papers/${qs ? `?${qs}` : ''}`)
  if (Array.isArray(res)) {
    return { papers: res }
  }
  return { papers: res?.papers ?? [] }
}

export async function fetchPaper(paperId: string): Promise<PaperDetail> {
  return api<PaperDetail>(`/mocktest/papers/${paperId}/`)
}

export async function startAttempt(paperId: string, runMode: 'exam' | 'practice' = 'exam'): Promise<AttemptState> {
  return api<AttemptState>(`/mocktest/papers/${paperId}/start/`, {
    method: 'POST',
    body: JSON.stringify({ run_mode: runMode }),
  })
}

export async function acceptInstructions(attemptId: string): Promise<AttemptState> {
  return api<AttemptState>(`/mocktest/attempts/${attemptId}/accept/`, {
    method: 'POST',
  })
}

export async function startWriting(attemptId: string): Promise<AttemptState> {
  return api<AttemptState>(`/mocktest/attempts/${attemptId}/writing/start/`, {
    method: 'POST',
  })
}

export async function acquireLease(
  attemptId: string,
  tabId: string,
  label = 'Browser Tab',
): Promise<{ epoch: number; expires_at: string; held_by_me: boolean; label: string }> {
  return api(`/mocktest/attempts/${attemptId}/lease/`, {
    method: 'POST',
    body: JSON.stringify({ tab_id: tabId, label }),
  })
}

export async function heartbeat(
  attemptId: string,
  epoch: number,
  position: number,
  events?: Array<{ type: string; position?: number; duration_ms?: number }>,
): Promise<ClockSyncResponse> {
  return api<ClockSyncResponse>(`/mocktest/attempts/${attemptId}/heartbeat/`, {
    method: 'POST',
    body: JSON.stringify({ epoch, position, events: events ?? [] }),
  })
}

export async function saveAnswers(
  attemptId: string,
  epoch: number,
  items: Array<{ position: number; answer?: unknown; flags?: { marked_for_review?: boolean } }>,
): Promise<Array<{ position: number; status: string }>> {
  return api(`/mocktest/attempts/${attemptId}/answers/`, {
    method: 'POST',
    body: JSON.stringify({ epoch, items }),
  })
}

export async function closeSection(
  attemptId: string,
  sectionKey: string,
  epoch: number,
): Promise<{ closed_section: string; next_section: string | null; remaining_ms: number }> {
  return api(`/mocktest/attempts/${attemptId}/sections/${sectionKey}/close/`, {
    method: 'POST',
    body: JSON.stringify({ epoch }),
  })
}

export async function submitAttempt(attemptId: string, epoch: number): Promise<AttemptResult> {
  return api<AttemptResult>(`/mocktest/attempts/${attemptId}/submit/`, {
    method: 'POST',
    body: JSON.stringify({ epoch }),
  })
}

export async function fetchAttemptState(attemptId: string): Promise<AttemptState> {
  return api<AttemptState>(`/mocktest/attempts/${attemptId}/`)
}

export async function fetchAttemptResult(attemptId: string): Promise<AttemptResult> {
  return api<AttemptResult>(`/mocktest/attempts/${attemptId}/result/`)
}

export async function fetchAttemptReview(
  attemptId: string,
  filterBy?: 'wrong' | 'skipped' | 'flagged',
): Promise<AttemptReview> {
  const qs = filterBy ? `?filter_by=${filterBy}` : ''
  return api<AttemptReview>(`/mocktest/attempts/${attemptId}/review/${qs}`)
}

export async function fetchSeriesList(subjectKey?: string): Promise<{ series: SeriesCard[] }> {
  const qs = subjectKey ? `?subject=${subjectKey}` : ''
  const res = await api<SeriesCard[] | { series: SeriesCard[] }>(`/mocktest/series/${qs}`)
  if (Array.isArray(res)) {
    return { series: res }
  }
  return { series: res?.series ?? [] }
}

export async function fetchMockSettings(): Promise<MockTestSettings> {
  return api<MockTestSettings>('/mocktest/settings/')
}

export async function updateMockSettings(payload: Partial<MockTestSettings>): Promise<MockTestSettings> {
  return api<MockTestSettings>('/mocktest/settings/', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
