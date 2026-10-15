import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Flag,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
  toast,
} from '@artha/design-system'
import * as React from 'react'

import { reportQuestion, type ReportQuestionPayload } from '../lib/api'

interface ReportErrorDialogProps {
  questionId: string
  trigger?: React.ReactNode
  onReported?: () => void
}

const REASONS: Array<{ value: ReportQuestionPayload['reason']; label: string }> = [
  { value: 'wrong_answer', label: 'Wrong answer key or explanation' },
  { value: 'typo', label: 'Typo or grammatical error' },
  { value: 'unclear', label: 'Unclear question statement' },
  { value: 'outdated_law', label: 'Outdated law or amendment' },
  { value: 'wrong_chapter', label: 'Wrong chapter or topic classification' },
  { value: 'duplicate', label: 'Duplicate question' },
  { value: 'copyright', label: 'Copyright or ownership concern' },
  { value: 'offensive', label: 'Inappropriate content' },
  { value: 'other', label: 'Other issue' },
]

export function ReportErrorDialog({ questionId, trigger, onReported }: ReportErrorDialogProps) {
  const [open, setOpen] = React.useState(false)
  const [reason, setReason] = React.useState<ReportQuestionPayload['reason']>('wrong_answer')
  const [message, setMessage] = React.useState('')
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      await reportQuestion(questionId, {
        reason,
        message: message.trim() || undefined,
      })
      toast.success('Thanks, we will tell you what we decide.')
      setOpen(false)
      setMessage('')
      onReported?.()
    } catch {
      toast.error('Could not submit report. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="ghost" size="sm" className="gap-1.5 text-xs text-muted-foreground hover:text-foreground">
            <Flag aria-hidden className="size-3.5" />
            Report error
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Report an issue with this question</DialogTitle>
          <DialogDescription>
            Our editorial team reviews every report. We will notify you once resolved.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <label htmlFor="report-reason" className="text-xs font-semibold text-foreground">
              What seems to be wrong?
            </label>
            <Select value={reason} onValueChange={(val) => setReason(val as ReportQuestionPayload['reason'])}>
              <SelectTrigger id="report-reason">
                <SelectValue placeholder="Select reason..." />
              </SelectTrigger>
              <SelectContent>
                {REASONS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="report-message" className="text-xs font-semibold text-foreground">
              Details (optional, up to 1,000 characters)
            </label>
            <Textarea
              id="report-message"
              value={message}
              onChange={(e) => setMessage(e.target.value.slice(0, 1000))}
              placeholder="Tell us what specifically is incorrect..."
              rows={4}
              maxLength={1000}
            />
            <p className="text-right text-xs text-muted-foreground">{message.length}/1000</p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting} disabled={isSubmitting}>
              Submit report
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
