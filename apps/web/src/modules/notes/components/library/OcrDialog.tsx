import {
  Button,
  CircleAlert,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Lock,
  ProgressBar,
  ScanText,
  SegmentedControl,
  UsageBar,
} from '@artha/design-system'

import { type DocumentSummary, isOcrRunning, type OcrLang } from '../../lib/document-types'
import { ocrOffer, ocrProgressText, resetDateText } from '../../lib/ocr-copy'
import type { Usage } from '../../lib/types'

type OcrDoc = Pick<
  DocumentSummary,
  'title' | 'status' | 'page_count' | 'ocr_pages_total' | 'ocr_pages_done' | 'ocr_status' | 'can_copy'
>

interface OcrDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  doc: OcrDoc
  usage?: Pick<Usage, 'limits' | 'used' | 'resets_on'>
  lang: OcrLang
  onLangChange: (lang: OcrLang) => void
  /** Hindi reading is on offer only when the server says it can do it (`capabilities.ocr_hindi`). */
  hindiAvailable?: boolean
  busy?: boolean
  /** A server refusal in plain words (not allowed, not ready, ...). */
  error?: string
  online: boolean
  /** `pages` is set when only part of the file is read ("1-120"). */
  onStart: (pages?: string) => void
}

/**
 * The OCR offer (FR-F03-49): how long it takes, how many of this month's OCR pages it uses, the language, and the ways out.
 * It also covers the states around it: locked, not allowed for a copy-restricted file, over the monthly allowance (with the
 * reset date and a "first N pages" option) and "already running".
 */
export function OcrDialog({
  open,
  onOpenChange,
  doc,
  usage,
  lang,
  onLangChange,
  hindiAvailable = true,
  busy,
  error,
  online,
  onStart,
}: OcrDialogProps) {
  const offer = ocrOffer(doc, usage)
  const running = isOcrRunning(doc.ocr_status) || doc.ocr_status === 'partial'
  const locked = doc.status === 'needs_password'
  const notAllowed = doc.can_copy === false
  const reset = resetDateText(usage?.resets_on)
  const startable = !locked && !notAllowed && !running && doc.ocr_status !== 'done' && online

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle className="flex items-center gap-2">
          <ScanText aria-hidden className="size-5" /> Make this PDF searchable
        </DialogTitle>
        <DialogDescription className="break-words">{doc.title}</DialogDescription>

        <div className="mt-4 space-y-4">
          {locked ? (
            <p className="flex items-start gap-2 text-sm">
              <Lock aria-hidden className="mt-0.5 size-4 shrink-0" />
              Locked: search and OCR need the password. Open the PDF and type its password first.
            </p>
          ) : notAllowed ? (
            <p className="flex items-start gap-2 text-sm">
              <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
              This file does not allow copying its text, so it cannot be read with OCR. You can still mark it with the
              area highlight, pen and notes.
            </p>
          ) : doc.ocr_status === 'done' ? (
            <p role="status" className="text-sm">
              This PDF is already searchable.
            </p>
          ) : running ? (
            <div className="space-y-2" role="status">
              <p className="text-sm">{ocrProgressText(doc.ocr_pages_done, doc.ocr_pages_total || offer.needed)}</p>
              <ProgressBar
                label="OCR progress"
                value={
                  offer.needed > 0 ? Math.round((doc.ocr_pages_done / (doc.ocr_pages_total || offer.needed)) * 100) : 0
                }
              />
              <p className="text-sm text-muted-foreground">
                You can keep reading. Pages become searchable as they finish.
              </p>
            </div>
          ) : (
            <>
              {offer.fits ? (
                <p className="text-base font-medium">{offer.summary}.</p>
              ) : (
                <div className="space-y-2" role="alert">
                  <p className="text-base font-medium">{offer.summary}.</p>
                  <p className="text-sm">
                    {offer.left > 0
                      ? `You have ${offer.left.toLocaleString('en-IN')} OCR pages left this month.`
                      : 'You have no OCR pages left this month.'}
                    {reset ? ` They reset on ${reset}.` : ''}
                  </p>
                </div>
              )}
              {usage ? (
                <UsageBar
                  label="OCR pages this month"
                  used={usage.used.ocr_pages ?? 0}
                  limit={usage.limits.ocr_pages_per_month ?? 0}
                  fullText="No OCR pages left"
                />
              ) : null}
              {offer.fits && hindiAvailable ? (
                <div className="space-y-2">
                  <span className="text-sm font-semibold">Language of the text</span>
                  <SegmentedControl
                    label="Language of the text"
                    value={lang}
                    onValueChange={onLangChange}
                    options={[
                      { value: 'eng', label: 'English' },
                      { value: 'eng+hin', label: 'English and Hindi' },
                    ]}
                  />
                  <p className="text-sm text-muted-foreground">
                    Choose English and Hindi only if the PDF has Hindi text. It takes longer. We remember your choice
                    for next time.
                  </p>
                </div>
              ) : null}
            </>
          )}

          {!online && startable === false && !locked && !notAllowed && !running && doc.ocr_status !== 'done' ? (
            <p className="text-sm text-muted-foreground">You are offline. OCR needs a connection.</p>
          ) : null}
          {error ? (
            <p role="alert" className="text-sm font-medium text-error-fg">
              {error}
            </p>
          ) : null}
        </div>

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {running ? 'Keep reading' : startable ? 'Not now' : 'Close'}
          </Button>
          {startable && !offer.fits && offer.partialRange ? (
            <Button onClick={() => onStart(offer.partialRange ?? undefined)} loading={busy}>
              Read the first {offer.left.toLocaleString('en-IN')} pages
            </Button>
          ) : null}
          {startable && offer.fits ? (
            <Button variant="cta" onClick={() => onStart()} loading={busy}>
              Make searchable
            </Button>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  )
}
