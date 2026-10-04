import { Alert, Button, LoaderCircle, TextField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { OTP_LENGTH, validateOtp } from '../lib/validation'

interface CodeFormProps {
  /** Where the code was sent, shown to the student. */
  email: string
  submitLabel?: string
  pending?: boolean
  error?: string
  resendSeconds: number
  resendPending?: boolean
  resendNotice?: string
  onSubmit: (code: string) => void
  onResend: () => void
  onChangeEmail?: () => void
}

/** One-time code entry with resend cooldown. Autofill friendly (iOS and Android read codes from the email). */
export function CodeForm({
  email,
  submitLabel = 'Verify and continue',
  pending,
  error,
  resendSeconds,
  resendPending,
  resendNotice,
  onSubmit,
  onResend,
  onChangeEmail,
}: CodeFormProps) {
  const [code, setCode] = useState('')
  const [fieldError, setFieldError] = useState<string>()

  function handle(e: FormEvent) {
    e.preventDefault()
    const problem = validateOtp(code)
    setFieldError(problem)
    if (!problem) onSubmit(code)
  }

  return (
    <form onSubmit={handle} noValidate className="space-y-4">
      <Alert variant="success">
        We sent a link and a {OTP_LENGTH} digit code to <strong className="break-all">{email}</strong>. Open the link,
        or type the code here.
      </Alert>
      <TextField
        label="Code"
        name="code"
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9 ]*"
        placeholder="123456"
        className="[&_input]:text-center [&_input]:text-xl [&_input]:tracking-[0.4em]"
        value={code}
        onChange={(e) => setCode(e.target.value)}
        error={fieldError}
        required
      />
      {error && <Alert variant="error">{error}</Alert>}
      {resendNotice && <Alert>{resendNotice}</Alert>}
      <Button type="submit" className="w-full" disabled={pending}>
        {pending && <LoaderCircle className="animate-spin" aria-hidden />}
        {submitLabel}
      </Button>
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
        <Button type="button" variant="link" onClick={onResend} disabled={resendSeconds > 0 || resendPending}>
          {resendSeconds > 0 ? `Resend in ${resendSeconds}s` : 'Resend code'}
        </Button>
        {onChangeEmail && (
          <Button type="button" variant="link" onClick={onChangeEmail}>
            Use a different email
          </Button>
        )}
      </div>
    </form>
  )
}
