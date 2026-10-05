import { Button } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { AuthCard } from '../components/AuthCard'
import { CodeForm } from '../components/CodeForm'
import { GoogleButton } from '../components/GoogleButton'
import { SignUpForm } from '../components/SignUpForm'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { useAuth } from '../hooks/useAuth'
import { useCooldown } from '../hooks/useCooldown'
import { resendSignupEmail, signUpWithPassword, verifyEmailCode } from '../lib/auth-api'
import { notify } from '../lib/notify'

export function SignupContainer() {
  const { user, configured, signInWithGoogle } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState<string>()
  const signUp = useAsyncAction()
  const verify = useAsyncAction()
  const resend = useAsyncAction()
  const cooldown = useCooldown()

  useEffect(() => {
    if (user) void navigate({ to: '/app', replace: true })
  }, [user, navigate])

  async function create({ email: address, password }: { email: string; password: string }) {
    const result = await signUp.run(() => signUpWithPassword(address, password))
    if (!result.error) {
      setEmail(address)
      cooldown.start()
      notify.confirmationSent(address)
    }
  }

  async function resendCode() {
    if (!email) return
    const result = await resend.run(() => resendSignupEmail(email))
    if (!result.error) {
      cooldown.start()
      notify.codeResent()
    }
  }

  const footer = (
    <div className="flex flex-wrap items-center justify-center gap-2">
      Already have an account?
      <Button variant="outline" size="sm" asChild>
        <Link to="/login">Sign in</Link>
      </Button>
    </div>
  )

  if (email) {
    return (
      <AuthCard title="Confirm your email" description="One last step to activate your account." footer={footer}>
        <CodeForm
          email={email}
          submitLabel="Confirm and continue"
          pending={verify.pending}
          error={verify.error}
          resendSeconds={cooldown.secondsLeft}
          resendPending={resend.pending}
          resendNotice={resend.status === 'success' ? 'We sent a new code.' : resend.error}
          onSubmit={(code) =>
            void verify.run(() => verifyEmailCode(email, code, 'signup')).then((r) => !r.error && notify.signedUp())
          }
          onResend={() => void resendCode()}
          onChangeEmail={() => {
            setEmail(undefined)
            verify.reset()
          }}
        />
        <p className="text-center text-xs text-muted-foreground">
          If this email already has an account, no code is sent. Sign in instead.
        </p>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title="Create your account"
      description="Free to start. Your plan and progress stay saved."
      footer={footer}
    >
      <GoogleButton onClick={() => void signInWithGoogle()} disabled={!configured} />
      <SignUpForm
        pending={signUp.pending}
        error={configured ? signUp.error : 'Sign-in is not configured yet. Add the Supabase env vars.'}
        onSubmit={(values) => void create(values)}
      />
    </AuthCard>
  )
}
