import {
  Button,
  CircleAlert,
  Label,
  LoaderCircle,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Textarea,
  toast,
  toastApiError,
} from '@artha/design-system'
import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { track } from '~/modules/observability'

import { reportSyllabusIssue } from '../lib/api'
import type { ReportNodeType } from '../lib/types'

const MIN = 5
const MAX = 1000

/** "Report a wrong syllabus item" (FR-10). Anonymous or signed in; the API rate limits it. */
export function ReportIssue({ nodeType, nodeId }: { nodeType: ReportNodeType; nodeId: string }) {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const mutation = useMutation({
    mutationFn: () => reportSyllabusIssue({ node_type: nodeType, node_id: nodeId, message: message.trim() }),
    onSuccess: () => {
      track('syllabus_issue_reported', { node_type: nodeType })
      setMessage('')
      setOpen(false)
      toast.success('Thanks. Our editors will review your report.', { id: 'syllabus-report' })
    },
    onError: (error) =>
      toastApiError(error, 'We could not send your report. Please try again.', { id: 'syllabus-report' }),
  })

  const tooShort = message.trim().length < MIN

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!tooShort) mutation.mutate()
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) mutation.reset()
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="ghost">
          <CircleAlert aria-hidden /> Report a wrong item
        </Button>
      </PopoverTrigger>
      <PopoverContent>
        <form onSubmit={submit} className="space-y-3">
          <Label htmlFor={`report-${nodeId}`}>What looks wrong?</Label>
          <Textarea
            id={`report-${nodeId}`}
            value={message}
            maxLength={MAX}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="For example: this chapter moved to Paper 2 in the new scheme."
          />
          <Button type="submit" className="w-full" disabled={tooShort || mutation.isPending}>
            {mutation.isPending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
            Send report
          </Button>
        </form>
      </PopoverContent>
    </Popover>
  )
}
