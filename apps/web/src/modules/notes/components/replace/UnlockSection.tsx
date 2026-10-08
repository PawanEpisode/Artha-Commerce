import { Button, LoaderCircle, Lock, PasswordField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

interface UnlockSectionProps {
  /** Where the locked PDF stands, in words. */
  statusText: string | null
  working: boolean
  canUnlock: boolean
  online: boolean
  /** Why the last request was refused (not the PDF's own failure). */
  error?: string
  /** Sends the password. The field is emptied as soon as it is sent. */
  onSubmit: (password: string) => void
}

/** In the details of a locked PDF: type its password once so its text can be searched. The password is not kept. */
export function UnlockSection({ statusText, working, canUnlock, online, error, onSubmit }: UnlockSectionProps) {
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  if (!statusText && !canUnlock) return null

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!password) return
    const sent = password
    setPassword('')
    setOpen(false)
    onSubmit(sent)
  }

  return (
    <div className="grid gap-2" data-slot="unlock-section">
      <span className="text-sm font-semibold">Search inside this PDF</span>
      {statusText ? (
        <p className="flex items-start gap-2 text-sm" role="status">
          {working ? (
            <LoaderCircle aria-hidden className="mt-0.5 size-4 shrink-0 animate-spin motion-reduce:animate-none" />
          ) : (
            <Lock aria-hidden className="mt-0.5 size-4 shrink-0" />
          )}
          <span>{statusText}</span>
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-error-fg">
          {error}
        </p>
      ) : null}
      {canUnlock && !open ? (
        <div>
          <Button variant="outline" className="min-h-11" onClick={() => setOpen(true)} disabled={!online}>
            <Lock aria-hidden /> Unlock for search
          </Button>
        </div>
      ) : null}
      {canUnlock && open ? (
        <form onSubmit={submit} className="grid gap-3" autoComplete="off">
          <PasswordField
            label="PDF password"
            hint="Used once to read the text, then discarded. We never keep it."
            value={password}
            autoComplete="off"
            maxLength={256}
            onChange={(e) => setPassword(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" className="min-h-11" disabled={!password || !online}>
              Unlock
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="min-h-11"
              onClick={() => {
                setPassword('')
                setOpen(false)
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : null}
    </div>
  )
}
