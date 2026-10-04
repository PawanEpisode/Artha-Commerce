import { Alert, Button } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { AuthCard } from '../components/AuthCard'
import { EmailForm } from '../components/EmailForm'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { useCooldown } from '../hooks/useCooldown'
import { requestPasswordReset } from '../lib/auth-api'

export function ForgotPasswordContainer() {
  const [email, setEmail] = useState<string>()
  const request = useAsyncAction()
  const cooldown = useCooldown()

  async function send(address: string) {
    const result = await request.run(() => requestPasswordReset(address))
    if (!result.error) {
      setEmail(address)
      cooldown.start()
    }
  }

  const footer = (
    <Link to="/login" className="font-semibold text-primary underline-offset-4 hover:underline">
      Back to sign in
    </Link>
  )

  if (email) {
    return (
      <AuthCard title="Check your inbox" footer={footer}>
        {/* Same message whether or not the address has an account: no account enumeration. */}
        <Alert variant="success">
          If an account exists for <strong className="break-all">{email}</strong>, we sent a link to reset the password.
          It works once and expires in 1 hour.
        </Alert>
        <Button
          type="button"
          variant="outline"
          className="w-full"
          disabled={cooldown.active || request.pending}
          onClick={() => void send(email)}
        >
          {cooldown.active ? `Send again in ${cooldown.secondsLeft}s` : 'Send the link again'}
        </Button>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title="Reset your password"
      description="Enter your email and we will send you a reset link."
      footer={footer}
    >
      <EmailForm
        submitLabel="Send reset link"
        pending={request.pending}
        error={request.error}
        onSubmit={(a) => void send(a)}
      />
    </AuthCard>
  )
}
