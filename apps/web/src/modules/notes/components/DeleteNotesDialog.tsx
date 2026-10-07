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

export const DELETE_WORD = 'DELETE'
export const isDeleteConfirmed = (typed: string) => typed.trim().toUpperCase() === DELETE_WORD

interface DeleteNotesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  pending: boolean
  failed: boolean
  onConfirm: () => void
}

/** "Delete all my notes": type the word to confirm. Nothing is deleted until the word matches. */
export function DeleteNotesDialog({ open, onOpenChange, pending, failed, onConfirm }: DeleteNotesDialogProps) {
  const [typed, setTyped] = useState('')
  const close = (next: boolean) => {
    if (pending) return
    if (!next) setTyped('')
    onOpenChange(next)
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (isDeleteConfirmed(typed)) onConfirm()
  }
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogTitle>Delete all your notes?</DialogTitle>
        <DialogDescription>
          This permanently deletes every note, version, tag and image you have saved, including the Trash. It cannot be
          undone. Export your notes first if you want a copy.
        </DialogDescription>
        <form onSubmit={submit} noValidate className="mt-4 space-y-4">
          <TextField
            label={`Type ${DELETE_WORD} to confirm`}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
          />
          {failed ? (
            <Alert variant="error">
              <span>We could not delete your notes. Check your connection and try again.</span>
            </Alert>
          ) : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => close(false)} disabled={pending}>
              Keep my notes
            </Button>
            <Button type="submit" variant="danger" disabled={!isDeleteConfirmed(typed) || pending}>
              {pending ? <LoaderCircle aria-hidden className="animate-spin" /> : null}
              Delete everything
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
