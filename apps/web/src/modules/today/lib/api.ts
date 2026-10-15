import { api, ApiError } from '~/lib/api'

import type { OpenResult } from './types'

/** 403 `feature_disabled`: the server-side `today_plan` flag is off for this user. Treated like the web flag off. */
export function isFeatureDisabled(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403 && error.code === 'feature_disabled'
}

/** The API error code of a rejected request, or null. */
export const errorCode = (error: unknown): string | null => (error instanceof ApiError ? (error.code ?? null) : null)

/** The app-open call: ensures today's plan exists and returns it. Idempotent, so it is also how the screen refreshes. */
export const openToday = () => api<OpenResult>('/today/open/', { method: 'POST', body: JSON.stringify({}) })
