import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  TextField,
  useToast,
} from '@artha/design-system'
import { useEffect, useState } from 'react'

import { useSplit, useUndo } from '../hooks/useSessionActions'
import { errorMessage } from '../lib/api'
import { fromLocalInput, toLocalInput } from '../lib/duration'
import type { StudySession } from '../lib/types'

/** Splits one session in two at a chosen moment. Offers an undo for ten seconds. */
export function SplitDialog({
  session,
  tz,
  onClose,
}: {
  session: StudySession | null
  tz: string
  onClose: () => void
}) {
  const [at, setAt] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const split = useSplit()
  const undo = useUndo()
  const toast = useToast()

  useEffect(() => {
    if (!session) return
    const mid = (Date.parse(session.started_at) + Date.parse(session.ended_at)) / 2
    setAt(toLocalInput(mid, tz))
    setMessage(null)
  }, [session, tz])

  if (!session) return null
  const submit = () => {
    split.mutate(
      { id: session.id, at: fromLocalInput(at, tz).toISOString() },
      {
        onSuccess: (r) => {
          toast.show({
            message: 'Session split in two.',
            actionLabel: 'Undo',
            onAction: () => undo.mutate({ token: r.undo_token }),
          })
          onClose()
        },
        onError: (e) => setMessage(errorMessage(e)),
      },
    )
  }
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogTitle>Split session</DialogTitle>
        <DialogDescription>Choose the moment where the first part ends and the second begins.</DialogDescription>
        <form
          className="mt-4 space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <TextField label="Split at" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />
          {message ? (
            <Alert variant="error">
              <span role="alert">{message}</span>
            </Alert>
          ) : null}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={split.isPending || !at}>
              Split
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
