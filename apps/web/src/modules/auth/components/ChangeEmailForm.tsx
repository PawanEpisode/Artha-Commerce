import { Alert, Button, LoaderCircle, TextField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { validateEmail } from '../lib/validation'

interface ChangeEmailFormProps {
  pending?: boolean
  error?: string
  onSubmit: (email: string) => void
}

export function ChangeEmailForm({ pending, error, onSubmit }: ChangeEmailFormProps) {
  const [email, setEmail] = useState('')
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
        label="New email address"
        type="email"
        name="new-email"
        autoComplete="email"
        inputMode="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={fieldError}
        required
      />
      {error && <Alert variant="error">{error}</Alert>}
      <Button type="submit" disabled={pending}>
        {pending && <LoaderCircle className="animate-spin" aria-hidden />}
        Send confirmation
      </Button>
    </form>
  )
}
