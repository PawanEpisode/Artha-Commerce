import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  LoaderCircle,
  SelectField,
  Textarea,
} from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import type { ReportReason } from '../lib/api'
import { REPORT_NOTE_MAX, REPORT_REASON_OPTIONS } from '../lib/decks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The card being reported, shown so she knows which one. */
  preview: string
  pending: boolean
  error: string | null
  onSubmit: (reason: ReportReason, note: string) => void
}

/** "This card is wrong or out of date" (FR-F15-52). The note is optional and reaches the editors, never analytics. */
export function ReportDialog({ open, onOpenChange, preview, pending, error, onSubmit }: Props) {
  const [reason, setReason] = useState<ReportReason>('wrong')
  const [note, setNote] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit(reason, note)
  }
  return (
    <Dialog open={open} onOpenChange={(next) => (pending ? undefined : onOpenChange(next))}>
      <DialogContent>
        <DialogTitle>Report this card</DialogTitle>
        <DialogDescription>Tell our editors what is wrong with: {preview} They read every report.</DialogDescription>
        <form onSubmit={submit} noValidate className="space-y-4">
          <div className="grid gap-2">
            <label htmlFor="report-reason" className="text-sm font-medium">
              What is the problem?
            </label>
            <SelectField
              id="report-reason"
              value={reason}
              onValueChange={(v) => setReason(v as ReportReason)}
              options={REPORT_REASON_OPTIONS}
            />
          </div>
          <div className="grid gap-2">
            <label htmlFor="report-note" className="text-sm font-medium">
              Anything else? (optional)
            </label>
            <Textarea
              id="report-note"
              value={note}
              maxLength={REPORT_NOTE_MAX}
              rows={3}
              onChange={(e) => setNote(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {note.length} of {REPORT_NOTE_MAX} characters
            </p>
          </div>
          {error ? <Alert variant="error">{error}</Alert> : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending} aria-busy={pending}>
              {pending ? <LoaderCircle aria-hidden className="animate-spin" /> : null}
              Send report
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
