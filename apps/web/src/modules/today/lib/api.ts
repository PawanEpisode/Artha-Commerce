import { api, ApiError } from '~/lib/api'
import { newClientId } from '~/modules/coverage'

import type {
  AddTaskBody,
  EditFields,
  OpenResult,
  Plan,
  Preview,
  SkipReason,
  SnoozeUntil,
  SwapResponse,
  TaskResponse,
  TodaySettings,
  UndoFrom,
  WeekDay,
} from './types'

export { newClientId }

/** 403 `feature_disabled`: the server-side `today_plan` flag is off for this user. Treated like the web flag off. */
export function isFeatureDisabled(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403 && error.code === 'feature_disabled'
}

/** The API error code of a rejected request, or null. */
export const errorCode = (error: unknown): string | null => (error instanceof ApiError ? (error.code ?? null) : null)

/** The human message of the error envelope, or `fallback`. */
export function errorMessage(error: unknown, fallback = 'That did not work. Please try again.'): string {
  if (error instanceof ApiError) {
    const message = (error.body as { error?: { message?: unknown } } | undefined)?.error?.message
    if (typeof message === 'string' && message) return message
  }
  return fallback
}

/** `details` of the error envelope (field errors, the current task of a 409, the allowed actions of a 422). */
export function errorDetails(error: unknown): Record<string, unknown> {
  if (error instanceof ApiError) {
    const details = (error.body as { error?: { details?: unknown } } | undefined)?.error?.details
    if (details && typeof details === 'object') return details as Record<string, unknown>
  }
  return {}
}

const post = <T>(path: string, body: unknown = {}) => api<T>(path, { method: 'POST', body: JSON.stringify(body) })

/** The app-open call: ensures today's plan exists and returns it. Idempotent, so it is also how the screen refreshes. */
export const openToday = () => post<OpenResult>('/today/open/')

export const markCelebrated = () =>
  post<{ version: number; server_time: string; celebrated_at: string }>('/today/plan/celebrated/')

/** A stored plan for a past date (read only); 404 `plan_not_generated` when there is none. */
export const getPlanFor = (date: string) => api<Plan>(`/today/plan/?date=${date}`)

export const getPreview = (date: string) => api<Preview>(`/today/preview/?date=${date}`)

export const getHistory = (from: string, to: string) =>
  api<{ days: WeekDay[] }>(`/today/history/?from=${from}&to=${to}`)

export const getSettings = () => api<TodaySettings>('/today/settings/')

// ---- task actions: every call carries a client id, so a retry is harmless -------------------------------------------------

const task = (id: string, action: string) => `/today/tasks/${id}/${action}/`

export const startTask = (id: string, clientId: string) =>
  post<TaskResponse>(task(id, 'start'), { client_id: clientId })

export const completeTask = (id: string, clientId: string, runManualAction = false) =>
  post<TaskResponse>(task(id, 'complete'), { client_id: clientId, run_manual_action: runManualAction })

export const skipTask = (id: string, clientId: string, reason?: SkipReason | null) =>
  post<TaskResponse>(task(id, 'skip'), { client_id: clientId, ...(reason ? { reason } : {}) })

export const snoozeTask = (id: string, clientId: string, until: SnoozeUntil) =>
  post<TaskResponse>(task(id, 'snooze'), { client_id: clientId, until })

export const swapTask = (id: string, clientId: string) => post<SwapResponse>(task(id, 'swap'), { client_id: clientId })

export const undoTask = (id: string, clientId: string, from: UndoFrom) =>
  post<TaskResponse>(task(id, 'undo'), { client_id: clientId, from_state: from })

export const addTask = (body: AddTaskBody) => post<TaskResponse>('/today/tasks/', body)

export const editTask = (id: string, body: EditFields & { version: number }) =>
  api<TaskResponse>(`/today/tasks/${id}/`, { method: 'PATCH', body: JSON.stringify(body) })

export const deleteTask = (id: string, clientId: string) =>
  api<TaskResponse>(`/today/tasks/${id}/?client_id=${clientId}`, { method: 'DELETE' })
