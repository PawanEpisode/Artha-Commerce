import {
  Button,
  CircleHelp,
  Download,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Trash2,
  UsageBar,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import type { DocumentQuotaDetails } from '../../lib/errors'
import { formatBytes, pluralize } from '../../lib/format'
import { resetDateText } from '../../lib/ocr-copy'
import { MIB } from '../../lib/upload-check'

export interface LargestDocument {
  id: string
  title: string
  bytes: number
}

interface QuotaSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  quota: DocumentQuotaDetails | null
  largest: readonly LargestDocument[]
  /** `usage.resets_on`, for the monthly kinds. */
  resetsOn?: string
  busyId?: string
  onDownload: (doc: LargestDocument) => void
  onDelete: (doc: LargestDocument) => void
  /** Hide the "Manage PDFs" link when the sheet is already on the library. */
  showLibraryLink?: boolean
}

const COPY = {
  storage: { title: 'Your PDF storage is full', unit: 'MB' },
  documents: { title: 'You have reached the number of PDFs your plan allows', unit: 'PDFs' },
  ocr: { title: "You have used this month's OCR pages", unit: 'pages' },
  export: { title: "You have reached this month's export limit", unit: 'exports' },
  marks: { title: 'This PDF has reached its limit of marks', unit: 'marks' },
} as const

/**
 * Shown when a quota blocks an upload, an OCR run or an export (FR-F03-01). It says what is used and what the limit is, then
 * offers a way out: the five largest PDFs with Open, Download original and Delete. Typed notes keep working, and it says so.
 */
export function QuotaSheet({
  open,
  onOpenChange,
  quota,
  largest,
  resetsOn,
  busyId,
  onDownload,
  onDelete,
  showLibraryLink = true,
}: QuotaSheetProps) {
  const [why, setWhy] = useState(false)
  if (!quota) return null
  const copy = COPY[quota.kind]
  const isBytes = quota.kind === 'storage'
  const reset = resetDateText(quota.resets_on ?? resetsOn)
  const monthly = quota.kind === 'ocr' || quota.kind === 'export'
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[90dvh] overflow-y-auto sm:mx-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{copy.title}</SheetTitle>
          <SheetDescription>
            {monthly
              ? `${reset ? `It resets on ${reset}.` : 'It resets at the start of next month.'} You can keep reading and marking meanwhile.`
              : 'Your typed notes keep working. Free some room to add more PDFs.'}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-5">
          <UsageBar
            label={isBytes ? 'PDF storage' : copy.unit === 'PDFs' ? 'PDFs' : 'Used this month'}
            used={isBytes ? Math.round(quota.used / MIB) : quota.used}
            limit={isBytes ? Math.round(quota.limit / MIB) : quota.limit}
            unit={copy.unit}
            fullText="Limit reached"
          />

          {!monthly && largest.length > 0 ? (
            <section aria-labelledby="largest-h" className="space-y-2">
              <h3 id="largest-h" className="text-sm font-semibold">
                Your largest PDFs
              </h3>
              <ul className="space-y-2">
                {largest.slice(0, 5).map((doc) => (
                  <li key={doc.id} className="space-y-2 rounded-xl border border-border bg-card p-3">
                    <p className="flex items-baseline justify-between gap-3">
                      <span className="min-w-0 truncate font-medium" title={doc.title}>
                        {doc.title}
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                        {formatBytes(doc.bytes)}
                      </span>
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" asChild>
                        <Link to="/app/notes/pdf/$docId" params={{ docId: doc.id }}>
                          Open
                        </Link>
                      </Button>
                      <Button size="sm" variant="outline" disabled={busyId === doc.id} onClick={() => onDownload(doc)}>
                        <Download aria-hidden /> Download original
                      </Button>
                      <Button size="sm" variant="danger" disabled={busyId === doc.id} onClick={() => onDelete(doc)}>
                        <Trash2 aria-hidden /> Delete
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {!monthly && largest.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Delete a PDF you no longer need from your library, or compress large scans before adding them.
            </p>
          ) : null}

          <div>
            <button
              type="button"
              aria-expanded={why}
              onClick={() => setWhy((v) => !v)}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg text-sm font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/40"
            >
              <CircleHelp aria-hidden className="size-4" /> Why is there a limit?
            </button>
            {why ? (
              <p className="mt-1 text-sm text-muted-foreground">
                Every PDF is stored safely for you and has to be checked, read and kept ready on every device. A fixed
                allowance for each plan keeps that fast for everyone. Your plan allows{' '}
                {isBytes ? `${Math.round(quota.limit / MIB)} MB` : pluralize(quota.limit, copy.unit.replace(/s$/, ''))}.
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2">
            {showLibraryLink && !monthly ? (
              <Button variant="outline" asChild>
                <Link to="/app/notes/library">Manage my PDFs</Link>
              </Button>
            ) : null}
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
