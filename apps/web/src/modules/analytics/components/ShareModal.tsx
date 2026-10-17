import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  toast,
} from '@artha/design-system'
import * as React from 'react'

import { useCreateShare } from '../hooks/useAnalytics'

interface ShareModalProps {
  reportId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ShareModal({ reportId, open, onOpenChange }: ShareModalProps) {
  const { mutate: createShare, isPending, error } = useCreateShare()
  const [shareUrl, setShareUrl] = React.useState<string | null>(null)
  const [copied, setCopied] = React.useState(false)

  React.useEffect(() => {
    if (open && reportId && !shareUrl) {
      createShare(
        { report_id: reportId, scopes: ['overview', 'readiness'] },
        {
          onSuccess: (data) => {
            const origin = window.location.origin
            setShareUrl(`${origin}/app/analytics/share/${data.token}`)
          },
        },
      )
    }
    if (!open) {
      setShareUrl(null)
      setCopied(false)
    }
  }, [open, reportId, shareUrl, createShare])

  const handleCopy = () => {
    if (shareUrl) {
      navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      toast.success('Share link copied to clipboard')
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Share Progress Report</DialogTitle>
          <DialogDescription>
            Generate a secure, read-only link to share your exam progress with mentors, parents, or study partners.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {error && (
            <Alert variant="error">{error instanceof Error ? error.message : 'Could not generate share link.'}</Alert>
          )}

          {isPending ? (
            <div className="text-text-subtle py-6 text-center text-xs">Creating secure share link...</div>
          ) : shareUrl ? (
            <div className="space-y-2">
              <Label htmlFor="share-public-url" className="text-text text-xs font-semibold">
                Public Read-Only URL:
              </Label>
              <div className="flex gap-2">
                <Input id="share-public-url" value={shareUrl} readOnly className="font-mono text-xs" />
                <Button variant="secondary" onClick={handleCopy} size="sm">
                  {copied ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <p className="text-text-subtle text-[11px]">
                Anyone with this token can view this frozen snapshot of your study report. Link expires in 7 days.
              </p>
            </div>
          ) : null}

          <div className="flex justify-end pt-2">
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Done
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
