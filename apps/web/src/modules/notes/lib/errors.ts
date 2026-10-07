import { ApiError } from '~/lib/api'

import type { NoteConflictDetail } from './types'

const envelope = (error: unknown) =>
  error instanceof ApiError
    ? (error.body as { error?: { code?: unknown; message?: unknown; details?: unknown } } | undefined)?.error
    : undefined

/** 403 `feature_disabled`: the server-side `notes` flag is off for this student. Same as the web flag being off. */
export const isFeatureDisabled = (error: unknown) =>
  error instanceof ApiError && error.status === 403 && envelope(error)?.code === 'feature_disabled'

export const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404

export function noteConflict(error: unknown): NoteConflictDetail | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null
  const e = envelope(error)
  return e?.code === 'note_conflict' && e.details ? (e.details as NoteConflictDetail) : null
}

export interface QuotaDetails {
  kind: 'notes' | 'tags' | 'storage'
  used: number
  limit: number
  plan: string
}

export function quotaExceeded(error: unknown): QuotaDetails | null {
  if (!(error instanceof ApiError) || error.status !== 429) return null
  const e = envelope(error)
  return e?.code === 'quota_exceeded'
    ? ((e.details as QuotaDetails | null) ?? { kind: 'notes', used: 0, limit: 0, plan: 'free' })
    : null
}

export interface BodyError {
  code: string
  message: string
  line?: number | null
}

/** 422 `invalid_body`: the server's lint errors, to show beside the editor. */
export function invalidBody(error: unknown): BodyError[] | null {
  if (!(error instanceof ApiError) || error.status !== 422) return null
  const e = envelope(error)
  if (e?.code !== 'invalid_body') return null
  return ((e.details as { errors?: BodyError[] } | null)?.errors ?? []) as BodyError[]
}

export const isTagExists = (error: unknown) =>
  error instanceof ApiError && error.status === 409 && envelope(error)?.code === 'tag_exists'
