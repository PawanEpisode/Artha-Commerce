import { Button, LoaderCircle, Tabs, TabsContent, TabsList, TabsTrigger } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { AuthCard } from '../components/AuthCard'
import { CodeForm } from '../components/CodeForm'
import { EmailForm } from '../components/EmailForm'
import { GoogleButton } from '../components/GoogleButton'
import { PasswordSignInForm } from '../components/PasswordSignInForm'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { useAuth } from '../hooks/useAuth'
import { useCooldown } from '../hooks/useCooldown'
import { useGoAfterAuth } from '../hooks/usePostAuth'
import { sendEmailCode, signInWithPassword, verifyEmailCode } from '../lib/auth-api'
import { notify } from '../lib/notify'

const signedInToast = (result: { error?: string }) => {
  if (!result.error) notify.signedIn()
}

export type LoginMethod = 'code' | 'password'

interface LoginContainerProps {
  method: LoginMethod
  next?: string
  onMethodChange: (method: LoginMethod) => void
}

export function LoginContainer({ method, next, onMethodChange }: LoginContainerProps) {
  const { user, configured, signInWithGoogle } = useAuth()
  const goAfterAuth = useGoAfterAuth()

  const [email, setEmail] = useState<string>()
  const [signingIn, setSigningIn] = useState(false)
  const handedOff = useRef(false)
  const send = useAsyncAction()
  const verify = useAsyncAction()
  const resend = useAsyncAction()
  const passwordLogin = useAsyncAction()
  const cooldown = useCooldown()

  useEffect(() => {
    if (user && !handedOff.current) void goAfterAuth(next)
  }, [user, next, goAfterAuth])

  async function submitCode(code: string) {
    if (!email) return
    handedOff.current = true
    const result = await verify.run(async () => {
      const verified = await verifyEmailCode(email, code)
      if (verified.error) return verified
      setSigningIn(true)
      await goAfterAuth(next)
      return verified
    })
    if (result.error) {
      handedOff.current = false
      setSigningIn(false)
      return
    }
    signedInToast(result)
  }

  async function sendCode(address: string) {
    const result = await send.run(() => sendEmailCode(address))
    if (!result.error) {
      setEmail(address)
      cooldown.start()
      notify.codeSent(address)
    }
  }

  async function resendCode() {
    if (!email) return
    const result = await resend.run(() => sendEmailCode(email))
    if (!result.error) {
      cooldown.start()
      notify.codeResent()
    }
  }

  const notConfigured = !configured ? 'Sign-in is not configured yet. Add the Supabase env vars.' : undefined

  return (
    <AuthCard
      title="Welcome to ArthaCommerce"
      description="Sign in to save your plan, notes and progress."
      footer={
        <div className="flex flex-wrap items-center justify-center gap-2">
          New here?
          <Button variant="outline" size="sm" asChild>
            <Link to="/signup">Create an account</Link>
          </Button>
        </div>
      }
    >
      <GoogleButton onClick={() => void signInWithGoogle(next)} disabled={!configured} />
      <Tabs
        value={method}
        onValueChange={(v) => {
          if (v === 'code' || v === 'password') onMethodChange(v)
        }}
      >
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="code">Email code</TabsTrigger>
          <TabsTrigger value="password">Password</TabsTrigger>
        </TabsList>
        <TabsContent value="code" className="pt-5">
          {email ? (
            signingIn ? (
              <p className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground" role="status">
                <LoaderCircle className="animate-spin" aria-hidden />
                Signing you in…
              </p>
            ) : (
              <CodeForm
                email={email}
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
                  resend.reset()
                }}
              />
            )
          ) : (
            <EmailForm
              submitLabel="Email me a code"
              pending={send.pending}
              error={notConfigured ?? send.error}
              onSubmit={(address) => void sendCode(address)}
            />
          )}
        </TabsContent>
        <TabsContent value="password" className="pt-5">
          <PasswordSignInForm
            pending={passwordLogin.pending}
            error={notConfigured ?? passwordLogin.error}
            onSubmit={({ email: address, password }) =>
              void passwordLogin.run(() => signInWithPassword(address, password)).then(signedInToast)
            }
          />
        </TabsContent>
      </Tabs>
    </AuthCard>
  )
}
