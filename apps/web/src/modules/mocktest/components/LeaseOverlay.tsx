import React from 'react'

interface LeaseOverlayProps {
  onTakeOver: () => void
  label?: string
}

export const LeaseOverlay: React.FC<LeaseOverlayProps> = ({ onTakeOver, label = 'another window' }) => {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-labelledby="lease-dialog-title"
    >
      <div className="w-full max-w-md space-y-4 rounded-2xl border bg-card p-6 text-center shadow-xl">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-rose-600 dark:bg-rose-950 dark:text-rose-400">
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
        </div>

        <h3 id="lease-dialog-title" className="text-lg font-bold text-foreground">
          Exam Session Active Elsewhere
        </h3>

        <p className="text-sm text-muted-foreground">
          This exam is open and active in {label}. To prevent accidental duplicate submissions and timer conflicts, only
          one tab can write answers.
        </p>

        <div className="pt-2">
          <button
            type="button"
            onClick={onTakeOver}
            className="min-h-[44px] w-full rounded-xl bg-primary px-4 py-2.5 font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Resume in This Tab
          </button>
        </div>
      </div>
    </div>
  )
}
