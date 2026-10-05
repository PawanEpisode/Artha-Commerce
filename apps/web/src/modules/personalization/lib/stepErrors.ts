import { ApiError } from '~/lib/api'

export interface StepFailure {
  /** Field messages from the server's validation (`details`), keyed by field name. */
  fields: Record<string, string>
  /** One sentence for the step as a whole. */
  message: string
}

const FALLBACK = 'We could not save that. Please try again.'

/** Turns a failed step save into inline messages: field errors where the server named a field, else one sentence. */
export function describeStepError(error: unknown): StepFailure {
  if (!(error instanceof ApiError)) return { fields: {}, message: FALLBACK }
  if (error.status === 0) return { fields: {}, message: 'You look offline. Check your connection and try again.' }
  if (error.status === 429) return { fields: {}, message: 'Too many changes. Wait a moment and try again.' }
  if (error.code === 'feature_disabled') {
    return { fields: {}, message: 'Personalised setup is not available yet. Please try again later.' }
  }
  const envelope = (error.body as { error?: { message?: string; details?: unknown } } | undefined)?.error
  const fields: Record<string, string> = {}
  const details = envelope?.details
  if (details && typeof details === 'object') {
    for (const [name, value] of Object.entries(details as Record<string, unknown>)) {
      const first = Array.isArray(value) ? value[0] : value
      if (typeof first === 'string') fields[name] = first
    }
  }
  const message = fields.detail ?? (error.status < 500 && envelope?.message ? envelope.message : FALLBACK)
  return { fields, message }
}
