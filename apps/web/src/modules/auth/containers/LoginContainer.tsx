import { Button, Tabs, TabsContent, TabsList, TabsTrigger } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { AuthCard } from '../components/AuthCard'
import { CodeForm } from '../components/CodeForm'
import { EmailForm } from '../components/EmailForm'
import { GoogleButton } from '../components/GoogleButton'
import { PasswordSignInForm } from '../components/PasswordSignInForm'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { useAuth } from '../hooks/useAuth'
import { useCooldown } from '../hooks/useCooldown'
import { sendEmailCode, signInWithPassword, verifyEmailCode } from '../lib/auth-api'
import { notify } from '../lib/notify'
import { safeNextPath } from '../lib/redirects'

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
  const navigate = useNavigate()
  const destination = safeNextPath(next)

  const [email, setEmail] = useState<string>()
  const send = useAsyncAction()
  const verify = useAsyncAction()
  const resend = useAsyncAction()
  const passwordLogin = useAsyncAction()
  const cooldown = useCooldown()

  useEffect(() => {
    if (user) void navigate({ to: destination, replace: true })
  }, [user, destination, navigate])

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
      <GoogleButton onClick={() => void signInWithGoogle(destination)} disabled={!configured} />
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
            <CodeForm
              email={email}
              pending={verify.pending}
              error={verify.error}
              resendSeconds={cooldown.secondsLeft}
              resendPending={resend.pending}
              resendNotice={resend.status === 'success' ? 'We sent a new code.' : resend.error}
              onSubmit={(code) => void verify.run(() => verifyEmailCode(email, code)).then(signedInToast)}
              onResend={() => void resendCode()}
              onChangeEmail={() => {
                setEmail(undefined)
                verify.reset()
                resend.reset()
              }}
            />
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
