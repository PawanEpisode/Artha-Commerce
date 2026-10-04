import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  LogOut,
  ThemeRadioGroup,
} from '@artha/design-system'
import { useState } from 'react'

import { ChangeEmailForm } from '../components/ChangeEmailForm'
import { CodeForm } from '../components/CodeForm'
import { NewPasswordForm } from '../components/NewPasswordForm'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { useAuth } from '../hooks/useAuth'
import { useCooldown } from '../hooks/useCooldown'
import { requestEmailChange, sendReauthCode, updatePassword } from '../lib/auth-api'

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

/** /app/account: change email, change password (with emailed code when the server asks for it), appearance, sign out. */
export function AccountContainer() {
  const { user, signOut } = useAuth()

  const emailChange = useAsyncAction()
  const [requestedEmail, setRequestedEmail] = useState<string>()

  const password = useAsyncAction()
  const reauth = useAsyncAction()
  const cooldown = useCooldown()
  const [pendingPassword, setPendingPassword] = useState<string>()

  async function changeEmail(address: string) {
    const result = await emailChange.run(() => requestEmailChange(address))
    if (!result.error) setRequestedEmail(address)
  }

  async function changePassword(next: string) {
    const result = await password.run(() => updatePassword(next))
    if (result.needsReauth) {
      // The server wants proof of a recent sign-in: email a code, then retry with it (Reauthentication template).
      setPendingPassword(next)
      const sent = await reauth.run(() => sendReauthCode())
      if (!sent.error) cooldown.start()
    }
  }

  async function confirmWithCode(code: string) {
    if (!pendingPassword) return
    const result = await password.run(() => updatePassword(pendingPassword, code))
    if (!result.error) setPendingPassword(undefined)
  }

  const waitingForCode = pendingPassword !== undefined && password.status !== 'success'

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6">
      <header>
        <h1 className="text-3xl font-extrabold">Account</h1>
        <p className="mt-1 text-muted-foreground">Signed in as {user?.email}</p>
      </header>

      <Section
        title="Appearance"
        description="Reading is the default. System follows the clock: light 6 am to 6 pm, dark after."
      >
        <ThemeRadioGroup className="sm:grid-cols-2" />
      </Section>

      <Section title="Email" description="We email a confirmation to the new address before the change applies.">
        {requestedEmail ? (
          <p role="status" className="text-sm">
            Check <strong className="break-all">{requestedEmail}</strong> and click the confirmation link. Until then
            your sign-in email stays {user?.email}.
          </p>
        ) : (
          <ChangeEmailForm
            pending={emailChange.pending}
            error={emailChange.error}
            onSubmit={(a) => void changeEmail(a)}
          />
        )}
      </Section>

      <Section title="Password" description="Set or change the password you use with your email.">
        {password.status === 'success' && !waitingForCode ? (
          <p role="status" className="text-sm">
            Password updated.
          </p>
        ) : waitingForCode ? (
          <CodeForm
            email={user?.email ?? 'your email'}
            submitLabel="Confirm and update password"
            pending={password.pending}
            error={password.error ?? reauth.error}
            resendSeconds={cooldown.secondsLeft}
            resendPending={reauth.pending}
            onSubmit={(code) => void confirmWithCode(code)}
            onResend={() => void reauth.run(() => sendReauthCode()).then((r) => !r.error && cooldown.start())}
            onChangeEmail={() => setPendingPassword(undefined)}
          />
        ) : (
          <NewPasswordForm
            submitLabel="Update password"
            pending={password.pending}
            error={password.error}
            onSubmit={(next) => void changePassword(next)}
          />
        )}
      </Section>

      <Section title="Session" description="Sign out on this device.">
        <Button variant="outline" onClick={() => void signOut()}>
          <LogOut aria-hidden /> Sign out
        </Button>
      </Section>
    </div>
  )
}
