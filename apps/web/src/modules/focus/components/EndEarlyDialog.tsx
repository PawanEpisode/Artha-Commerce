import { Button, Dialog, DialogContent, DialogDescription, DialogTitle, Label, Select } from '@artha/design-system'
import { useState } from 'react'

import { MIN_ROUND_SECONDS } from '../lib/presets'
import { type EndReason, REASON_OPTIONS } from '../lib/types'

interface Props {
  open: boolean
  /** Seconds studied so far in this round. */
  studiedSeconds: number
  busy: boolean
  onClose: () => void
  onEnd: (save: boolean, reason?: EndReason) => void
}

/** End a round early: keep what was studied (with a reason) or throw it away. Under a minute is never saved. */
export function EndEarlyDialog({ open, studiedSeconds, busy, onClose, onEnd }: Props) {
  const [reason, setReason] = useState<EndReason>('other')
  const tooShort = studiedSeconds < MIN_ROUND_SECONDS
  const minutes = Math.floor(studiedSeconds / 60)
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogTitle>End this round early?</DialogTitle>
        <DialogDescription>
          {tooShort
            ? 'Less than a minute is not saved.'
            : `You studied ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}. Save it as a partial round, or discard it.`}
        </DialogDescription>
        {tooShort ? null : (
          <div className="mt-4 space-y-1.5">
            <Label htmlFor="end-reason">What got in the way?</Label>
            <Select id="end-reason" value={reason} onChange={(e) => setReason(e.target.value as EndReason)}>
              {REASON_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>
        )}
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Keep going
          </Button>
          <Button variant="outline" onClick={() => onEnd(false)} disabled={busy}>
            Discard
          </Button>
          {tooShort ? null : (
            <Button onClick={() => onEnd(true, reason)} disabled={busy}>
              Save {minutes} min
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
