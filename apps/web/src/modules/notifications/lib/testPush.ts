import { isNotFound, isRateLimited } from './api'
import { TEST_COOLDOWN_MAX_SECONDS, TEST_COOLDOWN_SECONDS } from './limits'

/** What the "Send me a test" control is showing. */
export type TestStatus =
  | { kind: 'idle' }
  | { kind: 'sending' }
  | { kind: 'sent' }
  | { kind: 'rate_limited'; seconds: number }
  | { kind: 'device_gone' }
  | { kind: 'failed' }

/** Maps a failed test request to a status. A 429 rests the button for as long as the API asked, within bounds. */
export function statusFromError(error: unknown): TestStatus {
  if (isRateLimited(error)) {
    const asked = error.retryAfter ?? TEST_COOLDOWN_SECONDS
    return { kind: 'rate_limited', seconds: Math.min(Math.max(Math.ceil(asked), 1), TEST_COOLDOWN_MAX_SECONDS) }
  }
  if (isNotFound(error)) return { kind: 'device_gone' }
  return { kind: 'failed' }
}

/** Polite, calm wording for the live region. `null` means say nothing. */
export function testStatusMessage(status: TestStatus): string | null {
  switch (status.kind) {
    case 'idle':
      return null
    case 'sending':
      return 'Sending a test alert…'
    case 'sent':
      return 'Test sent. It should appear in a few seconds. If it does not, check that alerts are allowed for this site.'
    case 'rate_limited':
      return `That was a lot of tests in a row. You can send another in ${status.seconds} ${status.seconds === 1 ? 'second' : 'seconds'}.`
    case 'device_gone':
      return 'That device is no longer registered. Turn alerts on again for it.'
    case 'failed':
      return 'We could not send the test. Please try again in a moment.'
  }
}

/** Which device a test goes to: this browser when it is registered, else the most recently seen one. */
export function pickTestDevice<T extends { id: string; last_seen_at?: string | null }>(
  devices: readonly T[],
  currentId: string | null,
): T | null {
  const own = currentId ? devices.find((d) => d.id === currentId) : undefined
  if (own) return own
  return [...devices].sort((a, b) => (b.last_seen_at ?? '').localeCompare(a.last_seen_at ?? ''))[0] ?? null
}
