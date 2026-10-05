import { Alert, Button } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { AuthCard } from '../components/AuthCard'
import { NewPasswordForm } from '../components/NewPasswordForm'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { useAuth } from '../hooks/useAuth'
import { updatePassword } from '../lib/auth-api'
import { notify } from '../lib/notify'

/** Set a new password after a recovery link, or choose a first password after accepting an invitation. */
export function ResetPasswordContainer({ mode }: { mode?: 'invite' }) {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const save = useAsyncAction()
  const invite = mode === 'invite'

  useEffect(() => {
    if (save.status === 'success') {
      notify.passwordUpdated()
      void navigate({ to: '/app', replace: true })
    }
  }, [save.status, navigate])

  if (loading) {
    return <p className="text-muted-foreground">Loading…</p>
  }

  if (!user) {
    return (
      <AuthCard title="Link expired">
        <Alert variant="error">This link has expired or was already used. Request a new one.</Alert>
        <Button asChild className="w-full">
          <Link to="/auth/forgot-password">Request a new link</Link>
        </Button>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title={invite ? 'Welcome! Set your password' : 'Choose a new password'}
      description={invite ? 'You will use it to sign in next time.' : `Signing in as ${user.email ?? 'your account'}.`}
    >
      <NewPasswordForm
        submitLabel={invite ? 'Save password and continue' : 'Update password'}
        pending={save.pending}
        error={save.error}
        onSubmit={(password) => void save.run(() => updatePassword(password))}
      />
    </AuthCard>
  )
}
