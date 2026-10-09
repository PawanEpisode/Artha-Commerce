import { Button, LoaderCircle } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { AuthCard } from '../components/AuthCard'
import { CodeForm } from '../components/CodeForm'
import { GoogleButton } from '../components/GoogleButton'
import { SignUpForm } from '../components/SignUpForm'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { useAuth } from '../hooks/useAuth'
import { useCooldown } from '../hooks/useCooldown'
import { useGoAfterAuth } from '../hooks/usePostAuth'
import { resendSignupEmail, signUpWithPassword, verifyEmailCode } from '../lib/auth-api'
import { notify } from '../lib/notify'

export function SignupContainer() {
  const { user, configured, signInWithGoogle } = useAuth()
  const goAfterAuth = useGoAfterAuth()
  const [email, setEmail] = useState<string>()
  const [signingIn, setSigningIn] = useState(false)
  const handedOff = useRef(false)
  const signUp = useAsyncAction()
  const verify = useAsyncAction()
  const resend = useAsyncAction()
  const cooldown = useCooldown()

  useEffect(() => {
    if (user && !handedOff.current) void goAfterAuth()
  }, [user, goAfterAuth])

  async function submitCode(code: string) {
    if (!email) return
    handedOff.current = true
    const result = await verify.run(async () => {
      const verified = await verifyEmailCode(email, code, 'signup')
      if (verified.error) return verified
      setSigningIn(true)
      await goAfterAuth()
      return verified
    })
    if (result.error) {
      handedOff.current = false
      setSigningIn(false)
      return
    }
    notify.signedUp()
  }

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
        {signingIn ? (
          <p className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground" role="status">
            <LoaderCircle className="animate-spin" aria-hidden />
            Signing you in…
          </p>
        ) : (
          <CodeForm
            email={email}
            submitLabel="Confirm and continue"
            pending={verify.pending}
            error={verify.error}
            resendSeconds={cooldown.secondsLeft}
            resendPending={resend.pending}
            resendNotice={resend.status === 'success' ? 'We sent a new code.' : resend.error}
            onSubmit={(code) => void submitCode(code)}
            onResend={() => void resendCode()}
            onChangeEmail={() => {
              setEmail(undefined)
              verify.reset()
            }}
          />
        )}
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
