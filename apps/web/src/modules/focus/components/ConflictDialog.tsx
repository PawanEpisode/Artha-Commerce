import { Button, Dialog, DialogContent, DialogDescription, DialogTitle } from '@artha/design-system'

interface Props {
  open: boolean
  /** "stopwatch" or "pomodoro": the timer that is already running. */
  kind: 'stopwatch' | 'pomodoro' | null
  onClose: () => void
  /** Opens the timer that is running (a link in the container). */
  action?: React.ReactNode
}

/** Shown when a start is refused because another timer already runs (this device or another). */
export function ConflictDialog({ open, kind, onClose, action }: Props) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogTitle>A timer is already running</DialogTitle>
        <DialogDescription>
          {kind === 'stopwatch'
            ? 'Your stopwatch is running, maybe on another device. Only one timer can run at a time. Stop the stopwatch first.'
            : 'A focus round is already running, maybe on another device. We have loaded it here.'}
        </DialogDescription>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          {action}
        </div>
      </DialogContent>
    </Dialog>
  )
}
