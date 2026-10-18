import { api } from '~/lib/api'
import { flushQueue, QueuedOffline, writeOrQueue } from '~/lib/offline-queue/write'

import type {
  AnswerSavePayload,
  BookmarkRow,
  ChapterProgress,
  CreateSessionParams,
  MistakeReason,
  MistakeRow,
  SessionClockView,
  SessionRow,
  SessionView,
} from './types'

export { QueuedOffline }

export async function createSession(params: CreateSessionParams): Promise<SessionView> {
  return await api<SessionView>('/practice/sessions/', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export async function getSession(sessionId: string): Promise<SessionView> {
  return await api<SessionView>(`/practice/sessions/${sessionId}/`)
}

export async function listSessions(params: { cursor?: string; limit?: number; status?: string } = {}): Promise<{
  items: SessionRow[]
  next_cursor?: string
  total?: number
}> {
  const query = new URLSearchParams()
  if (params.cursor) query.set('cursor', params.cursor)
  if (params.limit) query.set('limit', String(params.limit))
  if (params.status) query.set('status', params.status)
  const qs = query.toString()
  return await api(`/practice/sessions/${qs ? `?${qs}` : ''}`)
}

export async function saveAnswer(
  sessionId: string,
  itemId: string,
  payload: AnswerSavePayload,
  clientId?: string,
): Promise<{ saved: boolean }> {
  const path = `/practice/sessions/${sessionId}/answers/${itemId}/`
  const body = {
    answer_json: {
      selected_option_ids: payload.selected_option_ids ?? [],
      numeric_value: payload.numeric_value ?? null,
    },
    client_ts: payload.client_ts ?? new Date().toISOString(),
    time_spent_ms: payload.time_spent_ms ?? 0,
    confidence: payload.confidence ?? null,
    flagged: payload.flagged ?? false,
    notes_md: payload.notes_md ?? '',
  }

  const cid = clientId || `ans_${sessionId}_${itemId}_${Date.now()}`

  return await writeOrQueue(
    {
      clientId: cid,
      method: 'POST',
      path,
      body,
      scope: 'practice',
      label: 'Save answer',
    },
    () => api<{ saved: boolean }>(path, { method: 'POST', body: JSON.stringify(body) }),
  )
}

export async function checkAnswer(
  sessionId: string,
  itemId: string,
  answer?: { selected_option_ids?: string[]; numeric_value?: number | null },
): Promise<{
  result: 'correct' | 'incorrect' | 'skipped' | 'partial'
  marks_awarded: number
  explanation_md: string
  correct_option_ids?: string[]
  numeric_key?: number
}> {
  return await api(`/practice/sessions/${sessionId}/answers/${itemId}/check/`, {
    method: 'POST',
    body: JSON.stringify({ answer_json: answer ?? {} }),
  })
}

export async function setMistakeReason(
  sessionId: string,
  itemId: string,
  reason: MistakeReason,
): Promise<{ saved: boolean }> {
  return await api(`/practice/sessions/${sessionId}/answers/${itemId}/mistake-reason/`, {
    method: 'POST',
    body: JSON.stringify({ mistake_reason: reason }),
  })
}

/** Starts the session clock (idempotent); answers the clock fields so the player need not refetch the session. */
export async function startSession(sessionId: string): Promise<SessionClockView> {
  return await api<SessionClockView>(`/practice/sessions/${sessionId}/start/`, { method: 'POST' })
}

/** The student's running or paused session, or null. Small enough to poll. */
export async function getActiveSession(): Promise<SessionClockView | null> {
  const res = await api<{ session: SessionClockView | null }>('/practice/sessions/active/')
  return res.session
}

export async function pauseSession(sessionId: string): Promise<{ status: string }> {
  return await api<{ status: string }>(`/practice/sessions/${sessionId}/pause/`, { method: 'POST' })
}

export async function resumeSession(sessionId: string): Promise<{ status: string }> {
  return await api<{ status: string }>(`/practice/sessions/${sessionId}/resume/`, { method: 'POST' })
}

export async function submitSession(sessionId: string): Promise<SessionView> {
  return await api<SessionView>(`/practice/sessions/${sessionId}/submit/`, { method: 'POST' })
}

export async function retakeSession(
  sessionId: string,
  scope: 'all' | 'wrong' | 'unattempted' | 'flagged' = 'all',
): Promise<SessionView> {
  return await api<SessionView>(`/practice/sessions/${sessionId}/retake/`, {
    method: 'POST',
    body: JSON.stringify({ scope }),
  })
}

export async function getChapterProgressBatch(chapterIds: string[]): Promise<Record<string, ChapterProgress>> {
  if (chapterIds.length === 0) return {}
  const qs = new URLSearchParams({ chapter_ids: chapterIds.join(',') }).toString()
  return await api<Record<string, ChapterProgress>>(`/practice/progress/chapters/?${qs}`)
}

export async function getMistakes(): Promise<{ items: MistakeRow[] }> {
  return await api<{ items: MistakeRow[] }>('/practice/mistakes/')
}

export async function getBookmarks(): Promise<{ items: BookmarkRow[] }> {
  return await api<{ items: BookmarkRow[] }>('/practice/bookmarks/')
}

export async function setQuestionState(
  questionId: string,
  state: { bookmarked?: boolean; notes?: string },
): Promise<{ saved: boolean }> {
  return await api<{ saved: boolean }>(`/practice/questions/${questionId}/state/`, {
    method: 'POST',
    body: JSON.stringify(state),
  })
}

export async function syncPracticeQueue(): Promise<void> {
  await flushQueue({ scope: 'practice' })
}
