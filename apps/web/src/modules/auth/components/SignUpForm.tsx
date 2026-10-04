import { Alert, Button, LoaderCircle, PasswordField, TextField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { PASSWORD_HINT, validateEmail, validatePassword } from '../lib/validation'

interface SignUpFormProps {
  pending?: boolean
  error?: string
  onSubmit: (values: { email: string; password: string }) => void
}

export function SignUpForm({ pending, error, onSubmit }: SignUpFormProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})

  function handle(e: FormEvent) {
    e.preventDefault()
    const next = { email: validateEmail(email), password: validatePassword(password) }
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
        name="new-password"
        autoComplete="new-password"
        hint={PASSWORD_HINT}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
        required
      />
      {error && <Alert variant="error">{error}</Alert>}
      <Button type="submit" className="w-full" disabled={pending}>
        {pending && <LoaderCircle className="animate-spin" aria-hidden />}
        Create account
      </Button>
    </form>
  )
}
