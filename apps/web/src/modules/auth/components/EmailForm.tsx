import { Alert, Button, LoaderCircle, TextField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { validateEmail } from '../lib/validation'

interface EmailFormProps {
  submitLabel: string
  pending?: boolean
  error?: string
  initialEmail?: string
  onSubmit: (email: string) => void
}

/** Single email field. Used for "email me a code" and "send reset link". Ephemeral input state only. */
export function EmailForm({ submitLabel, pending, error, initialEmail = '', onSubmit }: EmailFormProps) {
  const [email, setEmail] = useState(initialEmail)
  const [fieldError, setFieldError] = useState<string>()

  function handle(e: FormEvent) {
    e.preventDefault()
    const problem = validateEmail(email)
    setFieldError(problem)
    if (!problem) onSubmit(email)
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
        error={fieldError}
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
