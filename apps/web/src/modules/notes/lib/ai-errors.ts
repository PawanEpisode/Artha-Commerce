import { ApiError } from '~/lib/api'

import type { NotEnoughDetails } from './ai-types'
import { errorCode, invalidBody } from './errors'

export type AiFailure =
  | { reason: 'not_consented'; version?: string }
  | { reason: 'unavailable' }
  | { reason: 'budget' }
  | { reason: 'not_enough'; details: NotEnoughDetails }
  | { reason: 'quota'; used: number; limit: number; resetsOn?: string; kind?: string }
  | { reason: 'invalid_pages' }
  | { reason: 'nothing_to_do' }
  | { reason: 'not_openable' }
  | { reason: 'not_ready' }
  | { reason: 'invalid_body'; messages: string[] }
  | { reason: 'feature_off' }
  | { reason: 'other' }

const details = (error: unknown): Record<string, unknown> =>
  ((error instanceof ApiError
    ? (error.body as { error?: { details?: unknown } } | undefined)?.error?.details
    : undefined) as Record<string, unknown> | null | undefined) ?? {}

/** Turns an API error of the AI endpoints into something the screen can branch on. Never throws. */
export function classifyAiError(error: unknown): AiFailure {
  const code = errorCode(error)
  switch (code) {
    case 'ai_not_consented':
      return { reason: 'not_consented', version: String(details(error).version ?? '') || undefined }
    case 'ai_unavailable':
      return { reason: 'unavailable' }
    case 'ai_budget_exhausted':
      return { reason: 'budget' }
    case 'not_enough_material':
      return { reason: 'not_enough', details: details(error) as unknown as NotEnoughDetails }
    case 'quota_exceeded': {
      const d = details(error)
      return {
        reason: 'quota',
        used: Number(d.used) || 0,
        limit: Number(d.limit) || 0,
        resetsOn: typeof d.resets_on === 'string' ? d.resets_on : undefined,
        kind: typeof d.kind === 'string' ? d.kind : undefined,
      }
    }
    case 'not_ready':
      return { reason: 'not_ready' }
    case 'invalid_pages':
      return { reason: 'invalid_pages' }
    case 'not_scanned_or_no_pages':
      return { reason: 'nothing_to_do' }
    case 'locked':
    case 'ocr_not_allowed':
      return { reason: 'not_openable' }
    case 'feature_disabled':
      return { reason: 'feature_off' }
    case 'invalid_body':
      return { reason: 'invalid_body', messages: (invalidBody(error) ?? []).map((e) => e.message) }
    default:
      return { reason: 'other' }
  }
}
