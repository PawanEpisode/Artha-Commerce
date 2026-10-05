import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  LoaderCircle,
  TextField,
} from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { ReauthPrompt } from '~/modules/auth'

import { CONFIRM_WORD, describeAccountError, isConfirmed } from '../lib/accountData'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  pending: boolean
  error: unknown
  /** Attempts the deletion with the typed word. Resolves when the request settled either way. */
  onConfirm: () => void
}

/**
 * Two steps, one dialog: type the word, then (only if the server asks) prove it is you with an emailed code. The
 * server decides when a code is needed, so this never guesses from the clock.
 */
export function DeleteAccountDialog({ open, onOpenChange, pending, error, onConfirm }: Props) {
  const [typed, setTyped] = useState('')
  const failure = error ? describeAccountError(error, 'delete') : null
  const needsCode = failure?.kind === 'reauth'

  function close(next: boolean) {
    if (pending) return // never abandon a request that is deleting data
    if (!next) setTyped('')
    onOpenChange(next)
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (isConfirmed(typed)) onConfirm()
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogTitle>Delete your account?</DialogTitle>
        <DialogDescription>
          This permanently deletes your profile, picture, coverage, study time and focus history. It cannot be undone.
          Download your data first if you want a copy.
        </DialogDescription>

        {needsCode ? (
          <ReauthPrompt submitLabel="Confirm and delete" onVerified={onConfirm} onCancel={() => close(false)} />
        ) : (
          <form onSubmit={submit} noValidate className="space-y-4">
            <TextField
              label={`Type ${CONFIRM_WORD} to confirm`}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
            />
            {failure ? <Alert variant="error">{failure.message}</Alert> : null}
            <div className="flex flex-wrap justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => close(false)} disabled={pending}>
                Keep my account
              </Button>
              <Button type="submit" variant="danger" disabled={!isConfirmed(typed) || pending}>
                {pending ? <LoaderCircle aria-hidden className="animate-spin" /> : null}
                Delete everything
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
