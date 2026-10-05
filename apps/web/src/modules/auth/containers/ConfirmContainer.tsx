import { Alert, Button, LoaderCircle } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { AuthCard } from '../components/AuthCard'
import { useGoAfterAuth } from '../hooks/usePostAuth'
import { confirmTokenHash } from '../lib/auth-api'
import { isConfirmType, postConfirmPath } from '../lib/redirects'

interface ConfirmContainerProps {
  tokenHash?: string
  type?: string
  next?: string
}

/**
 * Landing page for links in our auth emails: /auth/confirm?token_hash=...&type=...
 * The token is verified here, in the browser, so email link scanners that only fetch the URL cannot use it up.
 */
export function ConfirmContainer({ tokenHash, type, next }: ConfirmContainerProps) {
  const navigate = useNavigate()
  const goAfterAuth = useGoAfterAuth()
  const started = useRef(false) // React Strict Mode runs effects twice in dev; a one-time token must be sent once.
  const [error, setError] = useState<string>()

  const valid = Boolean(tokenHash) && isConfirmType(type)

  useEffect(() => {
    if (!valid || started.current || !tokenHash || !isConfirmType(type)) return
    started.current = true
    void confirmTokenHash(tokenHash, type).then((result) => {
      if (result.error) setError(result.error)
      else if (type === 'recovery' || type === 'invite' || type === 'email_change') {
        void navigate({ to: postConfirmPath(type, next), replace: true })
      } else void goAfterAuth(next) // a sign-in: the destination rules decide (onboarding, deep link, last visit)
    })
  }, [valid, tokenHash, type, next, navigate, goAfterAuth])

  if (!valid || error) {
    return (
      <AuthCard
        title="This link did not work"
        footer={
          <Button variant="outline" size="sm" asChild>
            <Link to="/login">Back to sign in</Link>
          </Button>
        }
      >
        <Alert variant="error">{error ?? 'The link is incomplete. Open the latest email we sent you.'}</Alert>
        <Button asChild className="w-full">
          <Link to="/auth/forgot-password">Request a new link</Link>
        </Button>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Verifying">
      <p role="status" className="flex items-center justify-center gap-2 text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" aria-hidden /> Checking your link…
      </p>
    </AuthCard>
  )
}
