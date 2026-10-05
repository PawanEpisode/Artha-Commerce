import { Button } from '@artha/design-system'
import { useEffect, useRef } from 'react'

import { useAsyncAction } from '../hooks/useAsyncAction'
import { useAuth } from '../hooks/useAuth'
import { useCooldown } from '../hooks/useCooldown'
import { sendEmailCode, verifyEmailCode } from '../lib/auth-api'
import { CodeForm } from './CodeForm'

interface Props {
  /** The session now proves a fresh sign-in. */
  onVerified: () => void
  onCancel?: () => void
  submitLabel?: string
}

/**
 * "Confirm it is you": emails a sign-in code to the signed-in student and verifies it, which gives the session a fresh
 * authentication. Used before dangerous actions the server protects (account deletion). Sends the code once on mount.
 */
export function ReauthPrompt({ onVerified, onCancel, submitLabel = 'Confirm' }: Props) {
  const { user } = useAuth()
  const email = user?.email ?? ''
  const send = useAsyncAction()
  const verify = useAsyncAction()
  const cooldown = useCooldown()
  const started = useRef(false)

  useEffect(() => {
    if (started.current || !email) return
    started.current = true
    void send.run(() => sendEmailCode(email)).then((r) => !r.error && cooldown.start())
  }, [email, send, cooldown])

  async function submit(code: string) {
    const result = await verify.run(() => verifyEmailCode(email, code))
    if (!result.error) onVerified()
  }

  return (
    <div className="space-y-3">
      <CodeForm
        email={email}
        submitLabel={submitLabel}
        pending={verify.pending}
        error={verify.error ?? send.error}
        resendSeconds={cooldown.secondsLeft}
        resendPending={send.pending}
        onSubmit={(code) => void submit(code)}
        onResend={() => void send.run(() => sendEmailCode(email)).then((r) => !r.error && cooldown.start())}
      />
      {onCancel ? (
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      ) : null}
    </div>
  )
}
