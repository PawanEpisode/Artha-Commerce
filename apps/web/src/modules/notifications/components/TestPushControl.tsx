import { Button, Send } from '@artha/design-system'

import { type TestStatus, testStatusMessage } from '../lib/testPush'

/**
 * "Send me a test" with its outcome in a polite live region. The region is always in the page, so a screen reader
 * hears the change; the text is the only signal, which also covers people who do not see the notification arrive.
 */
export function TestPushControl({
  status,
  canSend,
  hasDevice,
  onSend,
}: {
  status: TestStatus
  canSend: boolean
  hasDevice: boolean
  onSend: () => void
}) {
  const message = testStatusMessage(status)
  return (
    <div className="space-y-2">
      <Button type="button" variant="outline" disabled={!canSend} loading={status.kind === 'sending'} onClick={onSend}>
        <Send aria-hidden /> Send me a test
      </Button>
      <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
        {message ?? (hasDevice ? '' : 'Turn on alerts on this device first, then you can send yourself a test.')}
      </p>
    </div>
  )
}
