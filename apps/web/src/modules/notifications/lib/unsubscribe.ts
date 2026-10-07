import { ApiError } from '~/lib/api'

export type UnsubscribeStatus = 'checking' | 'ready' | 'working' | 'done' | 'invalid' | 'error'

interface Inputs {
  token: string | undefined
  previewLoading: boolean
  previewError: unknown
  confirming: boolean
  confirmed: boolean
  confirmError: unknown
}

/** A link we did not sign (or an empty one) is `invalid`; anything else that fails (network, 5xx, throttle) is `error`, which can be retried. */
const isInvalid = (error: unknown) => error instanceof ApiError && error.status === 400

export function unsubscribeStatus(i: Inputs): UnsubscribeStatus {
  if (!i.token) return 'invalid'
  if (i.confirmed) return 'done'
  if (i.confirming) return 'working'
  if (i.confirmError) return isInvalid(i.confirmError) ? 'invalid' : 'error'
  if (i.previewLoading) return 'checking'
  if (i.previewError) return isInvalid(i.previewError) ? 'invalid' : 'error'
  return 'ready'
}
