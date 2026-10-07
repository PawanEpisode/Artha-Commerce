import { Button, FileDropzone, NotebookPen } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { UploadLimits } from '../../lib/upload-check'

interface LibraryEmptyProps {
  limits: UploadLimits
  online: boolean
  onFiles: (files: File[]) => void
}

const TIPS = [
  'A module or study material PDF: read it here and highlight what matters.',
  'A coaching PDF or class notes: they stay private to you.',
  'Scanned notes or handwritten pages: add them, then make them searchable.',
] as const

/** The first-time library: what to add, the size limits up front, a drop area, and a way to start a typed note instead. */
export function LibraryEmpty({ limits, online, onFiles }: LibraryEmptyProps) {
  return (
    <section
      aria-labelledby="library-empty-h"
      className="space-y-5 rounded-2xl border border-border bg-card p-5 sm:p-8"
    >
      <div className="space-y-2">
        <h2 id="library-empty-h" className="font-display text-2xl font-bold">
          Add your first PDF
        </h2>
        <p className="text-muted-foreground">
          Read it on any device, highlight it, and find your marks later by subject and chapter.
        </p>
      </div>
      <ul className="space-y-2 text-sm">
        {TIPS.map((tip) => (
          <li key={tip} className="flex gap-2">
            <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" />
            {tip}
          </li>
        ))}
      </ul>
      <FileDropzone
        accept=".pdf,application/pdf"
        title="Drop a PDF here or choose one"
        hint={`PDF only. Up to ${limits.maxFileMb} MB and ${limits.maxPages.toLocaleString('en-IN')} pages each, ${limits.maxStorageMb} MB in all.`}
        inputLabel="Choose a PDF to add"
        disabled={!online}
        reason={!online ? 'You are offline. Connect to the internet to upload.' : undefined}
        messages={{
          type: 'This does not look like a PDF. Choose a file that ends in .pdf.',
          count: 'Add one PDF at a time.',
        }}
        onFiles={onFiles}
      />
      <Button variant="ghost" asChild>
        <Link to="/app/notes/new">
          <NotebookPen aria-hidden /> Start a note instead
        </Link>
      </Button>
    </section>
  )
}
