import {
  Button,
  CircleAlert,
  FileDropzone,
  FileText,
  LoaderCircle,
  Lock,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  TextField,
} from '@artha/design-system'
import { useState } from 'react'

import { formatBytes, pluralize } from '../../lib/format'
import { type FileFacts, refusalText, type UploadLimits, type UploadRefusal } from '../../lib/upload-check'

export type UploadSheetState =
  | { step: 'choose' }
  | { step: 'checking'; name: string; bytes: number }
  | { step: 'ready'; file: FileFacts; encrypted: boolean }
  | { step: 'refused'; file: FileFacts; refusal: UploadRefusal }

interface UploadSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  state: UploadSheetState
  limits: UploadLimits
  online: boolean
  /** The student's own quota, for the line under the limits ("412 of 500 MB used"). */
  usedText?: string
  onFiles: (files: File[]) => void
  onUpload: () => void
  onChooseAnother: () => void
  /** A quota refusal opens the quota sheet from here. */
  onManageStorage: () => void
  /** "Replace edition": the sheet says what is being replaced and asks for an optional edition name. */
  replacing?: { title: string; label: string; onLabelChange: (label: string) => void }
}

const ACCEPT = '.pdf,application/pdf'

/**
 * Choose a PDF, see its name, size and page count after a quick check, then Upload (space is reserved on that tap). A file
 * over a limit is refused here, before any byte moves, with the limit and what to try.
 */
export function UploadSheet({
  open,
  onOpenChange,
  state,
  limits,
  online,
  usedText,
  onFiles,
  onUpload,
  onChooseAnother,
  onManageStorage,
  replacing,
}: UploadSheetProps) {
  const [help, setHelp] = useState(false)
  const limitsText = `PDF only. Up to ${limits.maxFileMb} MB and ${limits.maxPages.toLocaleString('en-IN')} pages each.`
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[90dvh] overflow-y-auto sm:mx-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{replacing ? 'Replace with a newer edition' : 'Upload a PDF'}</SheetTitle>
          <SheetDescription>
            {replacing
              ? `Choose the newer file for “${replacing.title}”. Your marks move to it where the words match. `
              : null}
            Your PDF is private to you.{' '}
            {usedText ?? `Your plan holds ${pluralize(limits.maxDocuments, 'PDF')} and ${limits.maxStorageMb} MB.`}
          </SheetDescription>
        </SheetHeader>

        {state.step === 'choose' ? (
          <FileDropzone
            accept={ACCEPT}
            title="Drop a PDF here or choose one"
            hint={limitsText}
            inputLabel="Choose a PDF to upload"
            disabled={!online}
            reason={!online ? 'You are offline. Connect to the internet to upload.' : undefined}
            messages={{
              type: 'This does not look like a PDF. Choose a file that ends in .pdf.',
              count: 'Add one PDF at a time.',
            }}
            onFiles={onFiles}
          />
        ) : null}

        {state.step === 'checking' ? (
          <div role="status" className="flex items-center gap-3 rounded-xl border border-border bg-card p-4">
            <LoaderCircle aria-hidden className="size-5 animate-spin motion-reduce:animate-none" />
            <p className="min-w-0 text-sm">
              <span className="block truncate font-semibold">{state.name}</span>
              <span className="text-muted-foreground">Checking the file · {formatBytes(state.bytes)}</span>
            </p>
          </div>
        ) : null}

        {state.step === 'ready' ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-xl border border-border bg-card p-4">
              <FileText aria-hidden className="mt-0.5 size-6 shrink-0 text-muted-foreground" />
              <p className="min-w-0 text-sm">
                <span className="block truncate font-semibold" title={state.file.name}>
                  {state.file.name}
                </span>
                <span className="text-muted-foreground">
                  {formatBytes(state.file.bytes)} ·{' '}
                  {state.file.pages !== null ? pluralize(state.file.pages, 'page') : 'pages counted after upload'}
                </span>
              </p>
            </div>
            {state.encrypted ? (
              <p className="flex items-start gap-2 text-sm">
                <Lock aria-hidden className="mt-0.5 size-4 shrink-0" />
                This PDF is locked. It is accepted, and opens with your password. Search and OCR need the password.
              </p>
            ) : null}
            {replacing ? (
              <TextField
                label="Name this edition (optional)"
                hint="For example: 2027 edition."
                value={replacing.label}
                maxLength={40}
                onChange={(e) => replacing.onLabelChange(e.target.value)}
              />
            ) : null}
            <p className="text-sm text-muted-foreground">{limitsText} Space is reserved when you tap Upload.</p>
          </div>
        ) : null}

        {state.step === 'refused' ? (
          <div className="space-y-3" role="alert">
            <p className="flex items-start gap-2 font-semibold">
              <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-error-fg" />
              {refusalText(state.refusal).title}
            </p>
            <p className="text-sm text-muted-foreground">{refusalText(state.refusal).hint}</p>
            <p className="truncate text-sm text-muted-foreground" title={state.file.name}>
              {state.file.name} · {formatBytes(state.file.bytes)}. Nothing was uploaded.
            </p>
            {state.refusal.reason === 'too_large' || state.refusal.reason === 'too_many_pages' ? (
              <div>
                <button
                  type="button"
                  aria-expanded={help}
                  onClick={() => setHelp((v) => !v)}
                  className="inline-flex min-h-11 items-center rounded-lg text-sm font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/40"
                >
                  How to shrink a PDF
                </button>
                {help ? (
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                    <li>
                      On a phone, open the PDF in your Files or Drive app and save a smaller copy, or print it to PDF at
                      a lower quality.
                    </li>
                    <li>On a computer, use Preview (Export, Quartz filter: Reduce File Size) or any PDF compressor.</li>
                    <li>Split a big module into chapters and upload each part.</li>
                  </ul>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        <SheetFooter>
          {state.step === 'refused' && state.refusal.reason === 'quota' ? (
            <Button onClick={onManageStorage}>Manage storage</Button>
          ) : null}
          {state.step === 'refused' || state.step === 'ready' ? (
            <Button variant="outline" onClick={onChooseAnother}>
              Choose another
            </Button>
          ) : null}
          {state.step === 'ready' ? (
            <Button variant="cta" onClick={onUpload} disabled={!online}>
              {replacing ? 'Replace' : 'Upload'}
            </Button>
          ) : null}
        </SheetFooter>
        {state.step === 'ready' && !online ? (
          <p className="mt-2 text-sm text-muted-foreground">You are offline. Upload needs a connection.</p>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
