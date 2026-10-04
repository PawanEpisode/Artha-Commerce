import { Alert, Button, LoaderCircle, PasswordField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { PASSWORD_HINT, validatePassword, validatePasswordMatch } from '../lib/validation'

interface NewPasswordFormProps {
  submitLabel: string
  pending?: boolean
  error?: string
  onSubmit: (password: string) => void
}

/** New password with confirmation. Used by reset password, invite acceptance and the account page. */
export function NewPasswordForm({ submitLabel, pending, error, onSubmit }: NewPasswordFormProps) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({})

  function handle(e: FormEvent) {
    e.preventDefault()
    const next = { password: validatePassword(password), confirm: validatePasswordMatch(password, confirm) }
    setErrors(next)
    if (!next.password && !next.confirm) onSubmit(password)
  }

  return (
    <form onSubmit={handle} noValidate className="space-y-4">
      <PasswordField
        label="New password"
        name="new-password"
        autoComplete="new-password"
        hint={PASSWORD_HINT}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
        required
      />
      <PasswordField
        label="Confirm new password"
        name="confirm-password"
        autoComplete="new-password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        error={errors.confirm}
        required
      />
      {error && <Alert variant="error">{error}</Alert>}
      <Button type="submit" className="w-full" disabled={pending}>
        {pending && <LoaderCircle className="animate-spin" aria-hidden />}
        {submitLabel}
      </Button>
    </form>
  )
}
