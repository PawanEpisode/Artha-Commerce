import { Button, Dialog, DialogContent, DialogDescription, DialogTitle } from '@artha/design-system'

import { formatDuration } from '~/modules/tracker'

interface Props {
  open: boolean
  plannedSeconds: number
  busy: boolean
  onAnswer: (count: boolean) => void
}

/**
 * The round ran out while the student was away. They decide whether it counts; it is then saved as "not verified" so
 * reports can leave it out. The dialog has no close button on purpose: the question needs an answer.
 */
export function AwayDialog({ open, plannedSeconds, busy, onAnswer }: Props) {
  return (
    <Dialog open={open}>
      <DialogContent onEscapeKeyDown={(e) => e.preventDefault()} onInteractOutside={(e) => e.preventDefault()}>
        <DialogTitle>Did you study through that round?</DialogTitle>
        <DialogDescription>
          The {formatDuration(plannedSeconds)} round ended while you were away from this screen. Count it only if you
          really studied.
        </DialogDescription>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button variant="outline" onClick={() => onAnswer(false)} disabled={busy}>
            No, discard it
          </Button>
          <Button onClick={() => onAnswer(true)} disabled={busy}>
            Yes, count it
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
