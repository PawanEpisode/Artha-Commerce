import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Lock,
  PasswordField,
} from '@artha/design-system'
import { type FormEvent, useEffect, useRef, useState } from 'react'

import type { PasswordReason } from '../../lib/pdf-engine'

export interface PasswordDialogProps {
  open: boolean
  /** `need` the first time, `incorrect` after a wrong try. */
  reason: PasswordReason
  /** Tries so far; from the third the dialog adds a hint. */
  attempt: number
  onSubmit: (password: string) => void
  /** Cancel returns to the library. */
  onCancel: () => void
}

export const HINT_AFTER_TRIES = 3

/**
 * The prompt for a PDF with a user password. The password lives only in this field and in the call to the engine: it is
 * cleared on submit, never put in the URL, storage or any request, and the browser is told not to remember it.
 */
export function PasswordDialog({ open, reason, attempt, onSubmit, onCancel }: PasswordDialogProps) {
  const [value, setValue] = useState('')
  const input = useRef<HTMLDivElement>(null)

  // A wrong password empties the field and puts the cursor back in it.
  useEffect(() => {
    setValue('')
    if (open) input.current?.querySelector('input')?.focus()
  }, [attempt, open])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!value) return
    const password = value
    setValue('')
    onSubmit(password)
  }

  const wrong = reason === 'incorrect'
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent onInteractOutside={(e) => e.preventDefault()}>
        <form onSubmit={submit} className="grid gap-4" autoComplete="off">
          <div className="grid gap-1.5">
            <DialogTitle className="flex items-center gap-2">
              <Lock className="size-5" aria-hidden />
              This PDF is locked
            </DialogTitle>
            <DialogDescription>Enter its password to open it. We never store or send the password.</DialogDescription>
          </div>
          <div ref={input}>
            <PasswordField
              label="Password"
              name="pdf-password"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              error={wrong ? 'That password did not work. Check it and try again.' : undefined}
              hint={
                attempt >= HINT_AFTER_TRIES
                  ? 'Passwords are case-sensitive. If you are unsure, ask whoever shared the file.'
                  : undefined
              }
            />
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" disabled={!value}>
              Unlock
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
