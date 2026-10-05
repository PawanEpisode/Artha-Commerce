import { Alert, Button, LoaderCircle, PasswordField, TextField } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { type FormEvent, useState } from 'react'

import { validateEmail } from '../lib/validation'

interface PasswordSignInFormProps {
  pending?: boolean
  error?: string
  /** Shown when the account exists but is not confirmed yet. */
  onResendConfirmation?: () => void
  onSubmit: (values: { email: string; password: string }) => void
}

export function PasswordSignInForm({ pending, error, onResendConfirmation, onSubmit }: PasswordSignInFormProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})

  function handle(e: FormEvent) {
    e.preventDefault()
    const next = { email: validateEmail(email), password: password ? undefined : 'Enter your password.' }
    setErrors(next)
    if (!next.email && !next.password) onSubmit({ email, password })
  }

  return (
    <form onSubmit={handle} noValidate className="space-y-4">
      <TextField
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        inputMode="email"
        placeholder="you@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={errors.email}
        required
      />
      <PasswordField
        label="Password"
        name="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
        required
      />
      {error && (
        <Alert variant="error">
          <p>{error}</p>
          {onResendConfirmation && (
            <Button type="button" variant="outline" size="sm" className="mt-2" onClick={onResendConfirmation}>
              Resend confirmation email
            </Button>
          )}
        </Alert>
      )}
      <Button type="submit" className="w-full" disabled={pending}>
        {pending && <LoaderCircle className="animate-spin" aria-hidden />}
        Sign in
      </Button>
      <Button variant="ghost" size="sm" className="w-full" asChild>
        <Link to="/auth/forgot-password">Forgot password?</Link>
      </Button>
    </form>
  )
}
