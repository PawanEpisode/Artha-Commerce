import { Button, LoaderCircle, TextField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { checkName, NAME_MAX } from '../lib/names'

interface Props {
  value: string
  pending: boolean
  /** A message from the server for this field (it can know more than the browser). */
  serverError?: string
  disabled?: boolean
  onSave: (name: string) => void
}

/** The name field of the Profile section. Online only (a name edit is never queued). */
export function NameForm({ value, pending, serverError, disabled, onSave }: Props) {
  const [draft, setDraft] = useState(value)
  const [touched, setTouched] = useState(false)
  const checked = checkName(draft)
  const unchanged = checked.ok && checked.name === value
  const error = touched && !checked.ok ? checked.message : serverError

  function submit(e: FormEvent) {
    e.preventDefault()
    setTouched(true)
    if (checked.ok && !unchanged) onSave(checked.name)
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3">
      <TextField
        label="Your name"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => setTouched(true)}
        autoComplete="name"
        maxLength={NAME_MAX + 20}
        error={error}
        disabled={disabled || pending}
      />
      <Button type="submit" disabled={disabled || pending || unchanged || (touched && !checked.ok)}>
        {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
        Save name
      </Button>
    </form>
  )
}
