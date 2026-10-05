import { api, ApiError } from '~/lib/api'
import { newClientId } from '~/modules/coverage'

import type { EndReason, FocusSettings, FocusState, Phase, SessionPage } from './types'

export { newClientId }

const json = (body: unknown) => JSON.stringify(body)
const send = <T>(method: string, path: string, body?: unknown) =>
  api<T>(path, { method, ...(body === undefined ? {} : { body: json(body) }) })

const code = (error: unknown): string | null => {
  if (!(error instanceof ApiError)) return null
  const c = (error.body as { error?: { code?: unknown } } | undefined)?.error?.code
  return typeof c === 'string' ? c : null
}

/** 403 `feature_disabled`: the server-side `focus_timer` flag is off for this user. */
export const isFeatureDisabled = (error: unknown) =>
  error instanceof ApiError && error.status === 403 && code(error) === 'feature_disabled'
export const errorCode = code

/** The latest timer a 409 `stale_version` carries, so the screen can adopt it without another request. */
export function staleTimer(error: unknown): FocusState['timer'] | undefined {
  if (!(error instanceof ApiError) || error.status !== 409) return undefined
  const details = (error.body as { error?: { details?: { timer?: FocusState['timer'] } } } | undefined)?.error?.details
  return details?.timer
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const m = (error.body as { error?: { message?: unknown } } | undefined)?.error?.message
    if (typeof m === 'string') return m
  }
  return 'That did not work. Please try again.'
}

export const getTimer = (alive = false) => api<FocusState>(`/focus/timer/${alive ? '?alive=1' : ''}`)
export const heartbeat = () => send<FocusState>('POST', '/focus/timer/heartbeat/')

export interface StartBody {
  client_id: string
  phase?: Phase
  preset?: string
  focus_minutes?: number
  short_break_minutes?: number
  long_break_minutes?: number
  rounds_before_long?: number
  subject_id?: string | null
  chapter_id?: string | null
  activity_type?: string
  at?: string
}
type Body = Record<string, unknown>

/** Path and body of each write, shared by the live call and the offline queue that replays it. */
export const focusRequest = {
  start: (body: StartBody) => ({ method: 'POST' as const, path: '/focus/timer/start/', body: body as unknown as Body }),
  pause: (body: { version?: number; at?: string }) => ({ method: 'POST' as const, path: '/focus/timer/pause/', body }),
  resume: (body: { version?: number; at?: string }) => ({
    method: 'POST' as const,
    path: '/focus/timer/resume/',
    body,
  }),
  extend: (body: { version?: number }) => ({ method: 'POST' as const, path: '/focus/timer/extend/', body }),
  skipBreak: (body: { version?: number }) => ({ method: 'POST' as const, path: '/focus/timer/skip-break/', body }),
  end: (body: { client_id?: string; version?: number; save: boolean; reason?: EndReason }) => ({
    method: 'POST' as const,
    path: '/focus/timer/end/',
    body,
  }),
}
type Req = { method: 'POST'; path: string; body: Body }
export const sendFocus = <T = FocusState>(req: Req) => send<T>(req.method, req.path, req.body)

export const completePhase = () => send<FocusState>('POST', '/focus/timer/complete/', {})
export const claimRound = (count: boolean, version?: number) =>
  send<FocusState>('POST', '/focus/timer/claim/', { count, version })
export const changeContext = (body: {
  version: number
  subject_id?: string | null
  chapter_id?: string | null
  activity_type?: string
}) => send<FocusState>('PATCH', '/focus/timer/context/', body)

export const getSettings = () => api<FocusSettings>('/focus/settings/')
export const putSettings = (patch: Partial<FocusSettings>) =>
  send<FocusSettings & { changed: string[] }>('PUT', '/focus/settings/', patch)

export const listSessions = (params: { from?: string; to?: string; cursor?: string; limit?: number }) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') q.set(k, String(v))
  const s = q.toString()
  return api<SessionPage>(`/focus/sessions/${s ? `?${s}` : ''}`)
}

export const exportData = () => api<Record<string, unknown>>('/focus/data/')
export const deleteData = () => api<void>('/focus/data/', { method: 'DELETE' })
