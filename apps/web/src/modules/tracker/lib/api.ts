import { api, ApiError } from '~/lib/api'
import { newClientId } from '~/modules/coverage'

import type {
  Breakdown,
  GoalEntry,
  GoalsPayload,
  Group,
  Heatmap,
  Hours,
  ManualInput,
  Series,
  SessionEdit,
  SessionPage,
  SplitBy,
  StopResult,
  StopwatchState,
  StudySession,
  Summary,
  TimeVsCoverage,
  TrackerSettings,
  WeeklySummary,
} from './types'

export { newClientId }

const json = (body: unknown) => JSON.stringify(body)
const send = <T>(method: string, path: string, body?: unknown) =>
  api<T>(path, { method, ...(body === undefined ? {} : { body: json(body) }) })

/** 403 `feature_disabled`: the server-side `time_tracker` flag is off for this user. Treated like the web flag off. */
export function isFeatureDisabled(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 403) return false
  return (error.body as { error?: { code?: unknown } } | undefined)?.error?.code === 'feature_disabled'
}

/** The API error code of a rejected request ("overlap", "too_old", ...), or null. */
export function errorCode(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null
  const body = error.body as { error?: { code?: unknown } } | undefined
  return typeof body?.error?.code === 'string' ? body.error.code : null
}

/** Field messages of a rejected request, flattened to one sentence for the form. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const body = error.body as { error?: { message?: unknown } } | undefined
    if (typeof body?.error?.message === 'string') return body.error.message
  }
  return 'That did not work. Please try again.'
}

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ''
}

// --- Stopwatch -----------------------------------------------------------------------------------------------
export const getStopwatch = (opts: { alive?: boolean; active?: boolean } = {}) =>
  api<StopwatchState>(`/tracking/stopwatch/${qs({ alive: opts.alive, active: opts.active })}`)

/** Path and body of each stopwatch write, shared by the live call and the offline queue that replays it. */
export const stopwatchRequest = {
  start: (body: {
    client_id: string
    subject_id?: string | null
    chapter_id?: string | null
    activity_type?: string
    at?: string
  }) => ({ method: 'POST' as const, path: '/tracking/stopwatch/start/', body }),
  pause: (body: { at?: string; version?: number }) => ({
    method: 'POST' as const,
    path: '/tracking/stopwatch/pause/',
    body,
  }),
  resume: (body: { at?: string; version?: number }) => ({
    method: 'POST' as const,
    path: '/tracking/stopwatch/resume/',
    body,
  }),
  stop: (body: { client_id?: string; end_at?: string; save?: boolean; version?: number }) => ({
    method: 'POST' as const,
    path: '/tracking/stopwatch/stop/',
    body,
  }),
}
type Req = { method: 'POST'; path: string; body: Record<string, unknown> }
export const sendStopwatch = <T>(req: Req) => send<T>(req.method, req.path, req.body)

export const changeContext = (body: {
  version: number
  subject_id?: string | null
  chapter_id?: string | null
  activity_type?: string
}) => send<StopwatchState>('PATCH', '/tracking/stopwatch/context/', body)
export const answerIdle = (answer: 'prompted' | 'still_studying') =>
  send<StopwatchState>('POST', '/tracking/stopwatch/idle/', { answer })

export type { StopResult }

// --- Sessions ------------------------------------------------------------------------------------------------
export const listSessions = (params: {
  from?: string
  to?: string
  subject_id?: string
  source?: string
  cursor?: string
  limit?: number
  include_notes?: boolean
}) => api<SessionPage>(`/tracking/sessions/${qs(params)}`)

export const manualRequest = (body: ManualInput) => ({
  method: 'POST' as const,
  path: '/tracking/sessions/',
  body: body as unknown as Record<string, unknown>,
})
export const addManual = (body: ManualInput) => send<StudySession>('POST', '/tracking/sessions/', body)
export const editSession = (id: string, body: SessionEdit) =>
  send<StudySession>('PATCH', `/tracking/sessions/${id}/`, body)
export const deleteSession = (id: string) =>
  send<{ undo_token: string; undo_until: string }>('DELETE', `/tracking/sessions/${id}/`)
export const undoAction = (undo_token: string, notes?: Record<string, string>) =>
  send<{ sessions: StudySession[] }>('POST', '/tracking/sessions/undo/', { undo_token, notes })
export const mergeSessions = (body: {
  session_ids: string[]
  subject_id?: string | null
  chapter_id?: string | null
  activity_type?: string
}) => send<{ session: StudySession; undo_token: string | null }>('POST', '/tracking/sessions/merge/', body)
export const splitSession = (id: string, at: string) =>
  send<{ sessions: StudySession[]; undo_token: string }>('POST', `/tracking/sessions/${id}/split/`, { at })

// --- Goals and settings --------------------------------------------------------------------------------------
export const getGoals = () => api<GoalsPayload>('/tracking/goals/')
export const putGoals = (goals: GoalEntry[]) => send<GoalsPayload>('PUT', '/tracking/goals/', { goals })
export const getSettings = () => api<TrackerSettings>('/tracking/settings/')
export const putSettings = (patch: Partial<TrackerSettings>) =>
  send<TrackerSettings & { changed_keys: string[] }>('PUT', '/tracking/settings/', patch)
export const resetSettings = () => send<TrackerSettings>('DELETE', '/tracking/settings/')

// --- Reports -------------------------------------------------------------------------------------------------
export interface ReportParams {
  from: string
  to: string
  verified_only?: boolean
}
const range = (p: ReportParams) => ({ from: p.from, to: p.to, verified_only: p.verified_only || undefined })

export const getSummary = (p: ReportParams & { compare?: boolean }) =>
  api<Summary>(`/tracking/reports/summary/${qs({ ...range(p), compare: p.compare })}`)
export const getSeries = (p: ReportParams & { group: Group; by?: SplitBy }) =>
  api<Series>(`/tracking/reports/series/${qs({ ...range(p), group: p.group, by: p.by })}`)
export const getBreakdown = (p: ReportParams & { by: SplitBy; parent_id?: string }) =>
  api<Breakdown>(`/tracking/reports/breakdown/${qs({ ...range(p), by: p.by, parent_id: p.parent_id })}`)
export const getHeatmap = (p: ReportParams) => api<Heatmap>(`/tracking/reports/heatmap/${qs(range(p))}`)
export const getHours = (p: ReportParams) => api<Hours>(`/tracking/reports/hours/${qs(range(p))}`)
export const getTimeVsCoverage = (p: ReportParams & { subject_id: string }) =>
  api<TimeVsCoverage>(`/tracking/reports/time-vs-coverage/${qs({ ...range(p), subject_id: p.subject_id })}`)
export const getWeeklySummary = (week_start?: string) =>
  api<WeeklySummary>(`/tracking/reports/weekly-summary/${qs({ week_start })}`)

/** Downloads a CSV through the authenticated client and hands it to the browser as a file. */
export async function downloadCsv(
  path: string,
  params: Record<string, string | number | boolean | undefined>,
  name: string,
) {
  const { getSupabase } = await import('~/lib/supabase')
  const { env } = await import('~/lib/env')
  const { data } = (await getSupabase()?.auth.getSession()) ?? { data: { session: null } }
  const token = data.session?.access_token
  const res = await fetch(`${env.VITE_API_URL}/api/v1${path}${qs(params)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} on ${path}`)
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export const exportData = () => api<Record<string, unknown>>('/tracking/data/')
export const deleteData = () => api<void>('/tracking/data/', { method: 'DELETE' })
