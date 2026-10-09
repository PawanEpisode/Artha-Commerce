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

export const ERASE_WORD = 'ERASE'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  pending: boolean
  error: string | null
  onConfirm: (word: string) => void
}

/** The server insists on the exact word `ERASE`; the button only opens once the word is typed. */
export function EraseDialog({ open, onOpenChange, pending, error, onConfirm }: Props) {
  const [typed, setTyped] = useState('')
  const ok = typed.trim() === ERASE_WORD
  const close = (next: boolean) => {
    if (pending) return // never walk away from a request that is deleting data
    if (!next) setTyped('')
    onOpenChange(next)
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (ok) onConfirm(ERASE_WORD)
  }
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogTitle>Erase all your revision data?</DialogTitle>
        <DialogDescription>
          Every card, deck, review, statistic and setting of your revision is deleted for good. Your account and your
          notes stay. Download your data first if you want a copy.
        </DialogDescription>
        <form onSubmit={submit} noValidate className="space-y-4">
          <TextField
            label={`Type ${ERASE_WORD} to confirm`}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
          />
          {error ? <Alert variant="error">{error}</Alert> : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" disabled={pending} onClick={() => close(false)}>
              Keep my data
            </Button>
            <Button type="submit" variant="danger" disabled={!ok || pending} aria-busy={pending}>
              {pending ? <LoaderCircle aria-hidden className="animate-spin" /> : null}
              Erase everything
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
