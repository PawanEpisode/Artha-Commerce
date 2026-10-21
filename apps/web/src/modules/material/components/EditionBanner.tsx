import { AlertCircle, ArrowRight, X } from '@artha/design-system'
import React from 'react'

interface EditionBannerProps {
  currentEditionLabel: string
  latestEditionLabel: string
  onCompare: () => void
  onSwitchLatest: () => void
  onDismiss: () => void
}

export const EditionBanner: React.FC<EditionBannerProps> = ({
  currentEditionLabel,
  latestEditionLabel,
  onCompare,
  onSwitchLatest,
  onDismiss,
}) => {
  return (
    <div
      role="alert"
      className="flex flex-col justify-between gap-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 sm:flex-row sm:items-center sm:p-5"
    >
      <div className="flex flex-1 items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">
            You are viewing the {currentEditionLabel} study material.
          </p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            The Institute has released the {latestEditionLabel} edition. You can review all additions, modifications,
            and deletions, or switch your active edition.
          </p>
        </div>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2 self-start sm:self-auto">
        <button
          type="button"
          onClick={onCompare}
          className="min-h-[44px] rounded-xl border border-border bg-background px-3.5 py-1.5 text-xs font-semibold text-foreground hover:bg-muted"
        >
          View What Changed
        </button>
        <button
          type="button"
          onClick={onSwitchLatest}
          className="inline-flex min-h-[44px] items-center gap-1.5 rounded-xl bg-foreground px-3.5 py-1.5 text-xs font-semibold text-background hover:opacity-90"
        >
          <span>Switch to {latestEditionLabel}</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-muted-foreground hover:text-foreground"
          aria-label="Dismiss banner"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
