import { ArrowUpRight, Download, FileText, X } from '@artha/design-system'
import React, { useState } from 'react'

export interface PdfViewerModalProps {
  title: string
  pdfUrl: string
  subtitle?: string
  isOpen: boolean
  onClose: () => void
}

export const PdfViewerModal: React.FC<PdfViewerModalProps> = ({
  title,
  pdfUrl,
  subtitle = 'Official Solution Sheet',
  isOpen,
  onClose,
}) => {
  const [isLoading, setIsLoading] = useState(true)

  if (!isOpen || !pdfUrl) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="pdf-modal-title"
      className="fixed inset-0 z-50 flex animate-in items-center justify-center bg-black/60 p-3 backdrop-blur-xs duration-150 fade-in sm:p-6"
    >
      <div className="relative flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-3xl border bg-card shadow-2xl">
        {/* Modal Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-border bg-muted/40 px-5 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="shrink-0 rounded-xl bg-primary/10 p-2 text-primary">
              <FileText className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold tracking-wider text-primary uppercase">{subtitle}</div>
              <h2 id="pdf-modal-title" className="truncate text-base font-bold text-foreground sm:text-lg">
                {title}
              </h2>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <a
              href={pdfUrl}
              download
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-[36px] items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-muted"
              title="Download PDF"
            >
              <Download className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Download</span>
            </a>

            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-[36px] items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-muted"
              title="Open in new window"
            >
              <ArrowUpRight className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Pop Out</span>
            </a>

            <button
              type="button"
              onClick={onClose}
              aria-label="Close viewer"
              className="flex min-h-[36px] min-w-[36px] items-center justify-center rounded-xl p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* PDF Viewer Body */}
        <div className="relative w-full flex-1 overflow-hidden bg-muted/20">
          {isLoading && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center space-y-3 bg-card/80 backdrop-blur-xs">
              <div className="h-8 w-8 animate-spin rounded-full border-3 border-primary border-t-transparent" />
              <p className="text-sm font-semibold text-muted-foreground">Loading official document viewer...</p>
            </div>
          )}

          <iframe
            src={`${pdfUrl}#toolbar=1&navpanes=1`}
            title={title}
            className="h-full w-full border-0"
            onLoad={() => setIsLoading(false)}
          />
        </div>
      </div>
    </div>
  )
}
