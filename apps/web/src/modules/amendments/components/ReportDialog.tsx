import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
  TriangleAlert,
} from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { useCardActions } from '../hooks/useCardActions'

interface Props {
  publicId: string
  cardTitle: string
}

export function ReportDialog({ publicId, cardTitle }: Props) {
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState('wrong_change')
  const [message, setMessage] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const { fileReport, isReporting } = useCardActions()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!message.trim()) return
    try {
      await fileReport(publicId, kind, message)
      setSubmitted(true)
      setTimeout(() => {
        setOpen(false)
        setSubmitted(false)
        setMessage('')
      }, 1500)
    } catch {
      // Error handled by mutation
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className="text-xs text-muted-foreground underline underline-offset-2 transition-colors hover:text-foreground"
        >
          Report issue
        </button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <TriangleAlert className="h-4 w-4 text-amber-500" />
            Report an issue with this card
          </DialogTitle>
          <DialogDescription className="text-xs">{cardTitle}</DialogDescription>
        </DialogHeader>

        {submitted ? (
          <div className="py-6 text-center text-sm font-medium text-emerald-600">
            Thank you! Your report has been submitted for editorial review.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <label htmlFor="report-issue-type" className="text-xs font-medium">
                Issue type
              </label>
              <Select value={kind} onValueChange={(val) => setKind(val ?? 'wrong_change')}>
                <SelectTrigger id="report-issue-type" className="w-full text-xs">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="wrong_change">Incorrect change description</SelectItem>
                  <SelectItem value="wrong_applicability">Wrong attempt applicability</SelectItem>
                  <SelectItem value="wrong_mapping">Wrong chapter or paper mapping</SelectItem>
                  <SelectItem value="missing_change">Missing provision details</SelectItem>
                  <SelectItem value="broken_link">Broken official link or page</SelectItem>
                  <SelectItem value="other">Other issue</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="report-issue-details" className="text-xs font-medium">
                Details
              </label>
              <Textarea
                id="report-issue-details"
                placeholder="Describe what looks incorrect..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={3}
                className="text-xs"
                required
              />
            </div>

            <DialogFooter className="gap-2 sm:gap-0">
              <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={isReporting || !message.trim()}>
                {isReporting ? 'Submitting...' : 'Submit Report'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
