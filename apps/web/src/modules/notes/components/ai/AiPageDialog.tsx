import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  LoaderCircle,
} from '@artha/design-system'

import type { AiConsentText } from '../../lib/ai-types'
import { ConsentPanel } from './ConsentPanel'

interface AiPageDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  page: number
  /** Set while the student has not agreed yet: the consent comes first. */
  consentText?: AiConsentText
  consentPending: boolean
  consentFailed: boolean
  onAgree: () => void
  allowance: string
  /** False when the plan has no AI pages or they are used up. */
  canStart: boolean
  busy: boolean
  error?: string
  onStart: () => void
}

/** Two steps in one dialog: agree to how AI help works (once), then confirm the page and what it costs. */
export function AiPageDialog({
  open,
  onOpenChange,
  page,
  consentText,
  consentPending,
  consentFailed,
  onAgree,
  allowance,
  canStart,
  busy,
  error,
  onStart,
}: AiPageDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (busy ? undefined : onOpenChange(next))}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto">
        <DialogTitle>Improve page {page} with AI</DialogTitle>
        <DialogDescription>
          AI reads a picture of this page and replaces the text OCR found. Tesseract stays the default for everything
          else.
        </DialogDescription>
        {consentText ? (
          <ConsentPanel
            text={consentText}
            pending={consentPending}
            failed={consentFailed}
            onAgree={onAgree}
            onCancel={() => onOpenChange(false)}
          />
        ) : (
          <div className="mt-4 space-y-4">
            <p className="text-sm text-muted-foreground">{allowance}</p>
            {error ? <Alert variant="error">{error}</Alert> : null}
            <div className="flex flex-wrap gap-3">
              <Button onClick={onStart} disabled={!canStart || busy}>
                {busy ? <LoaderCircle aria-hidden className="animate-spin" /> : null} Read this page with AI
              </Button>
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
                Not now
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
