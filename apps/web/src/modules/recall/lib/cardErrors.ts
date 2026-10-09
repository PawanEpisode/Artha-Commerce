import { ApiError } from '~/lib/api'

import type { FieldIssue, Fields } from './cardKinds'

export type CardFailure =
  | { kind: 'network' }
  | { kind: 'duplicate'; cardId: string | null }
  | { kind: 'conflict'; serverFields: Fields; rev: number | null }
  | { kind: 'invalid'; issues: FieldIssue[] }
  | { kind: 'quota'; message: string }
  | { kind: 'deleted' }
  | { kind: 'throttled' }
  | { kind: 'other'; message: string | null }

const details = (e: ApiError): Record<string, unknown> => {
  const d = (e.body as { error?: { details?: unknown } } | undefined)?.error?.details
  return d && typeof d === 'object' ? (d as Record<string, unknown>) : {}
}

const message = (e: ApiError): string | null => {
  const m = (e.body as { error?: { message?: unknown } } | undefined)?.error?.message
  return typeof m === 'string' && m.length < 200 ? m : null
}

const asFields = (v: unknown): Fields => {
  const out: Fields = {}
  if (v && typeof v === 'object') for (const [k, val] of Object.entries(v)) if (typeof val === 'string') out[k] = val
  return out
}

/** What went wrong with a card write, in the few shapes the screens react to. */
export function cardFailure(error: unknown): CardFailure {
  if (!(error instanceof ApiError)) return { kind: 'network' }
  if (error.status === 0) return { kind: 'network' }
  const d = details(error)
  switch (error.code) {
    case 'duplicate_card':
      return { kind: 'duplicate', cardId: typeof d.card_id === 'string' ? d.card_id : null }
    case 'edit_conflict':
      return {
        kind: 'conflict',
        serverFields: asFields(d.server_fields),
        rev: typeof d.rev === 'number' ? d.rev : null,
      }
    case 'invalid_fields': {
      const raw = Array.isArray(d.errors) ? d.errors : []
      const issues = raw.flatMap((r): FieldIssue[] => {
        const x = r as Partial<FieldIssue>
        return typeof x.field === 'string' && typeof x.message === 'string'
          ? [{ field: x.field, code: String(x.code ?? ''), message: x.message }]
          : []
      })
      return { kind: 'invalid', issues }
    }
    case 'quota_exceeded':
      return { kind: 'quota', message: message(error) ?? 'You have reached the card limit of your plan.' }
    case 'card_deleted':
      return { kind: 'deleted' }
    default:
      if (error.status === 429) return { kind: 'throttled' }
      if (error.status >= 500 || error.status === 408) return { kind: 'network' }
      return { kind: 'other', message: message(error) }
  }
}
