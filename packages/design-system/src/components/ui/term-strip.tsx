import * as React from 'react'

import { cn } from '../../lib/utils'

export interface TermSittingItem {
  termCode: string
  paperKind?: string
  marks?: number
  isAsked?: boolean
  isCarried?: boolean
}

export interface TermStripProps extends React.HTMLAttributes<HTMLDivElement> {
  sittings: TermSittingItem[]
  compact?: boolean
}

/**
 * Visual strip representing past exam sittings.
 * Each cell shows marks (or dash for unasked) with an accessible aria-label.
 * Never colour-only (PRD 7.4).
 */
export function TermStrip({ sittings, compact = false, className, ...props }: TermStripProps) {
  if (!sittings || sittings.length === 0) {
    return (
      <div className={cn('text-xs text-muted-foreground italic', className)} {...props}>
        No historical sittings recorded
      </div>
    )
  }

  return (
    <div
      role="group"
      aria-label="Past exam sittings"
      className={cn('inline-flex flex-wrap items-center gap-1', className)}
      {...props}
    >
      {sittings.map((sitting, idx) => {
        const isAsked = sitting.isAsked ?? (sitting.marks ?? 0) > 0
        const marksStr = sitting.marks !== undefined ? `${sitting.marks}m` : '—'
        const kindLabel = sitting.paperKind ? ` (${sitting.paperKind.toUpperCase()})` : ''
        const ariaText = isAsked
          ? `${sitting.termCode}${kindLabel}: ${marksStr} asked${sitting.isCarried ? ' (carried from older scheme)' : ''}`
          : `${sitting.termCode}${kindLabel}: Not asked`

        return (
          <span
            key={`${sitting.termCode}-${idx}`}
            aria-label={ariaText}
            title={ariaText}
            className={cn(
              'inline-flex flex-col items-center justify-center rounded border font-mono font-medium transition-colors select-none',
              compact ? 'h-6 px-1.5 text-[10px]' : 'h-7 min-w-9 px-2 text-xs',
              isAsked
                ? 'border-primary/30 bg-primary/10 font-semibold text-primary'
                : 'border-muted bg-muted/40 text-muted-foreground/60',
            )}
          >
            <span className="leading-tight">{isAsked ? marksStr : '—'}</span>
            {!compact && (
              <span className="mt-0.5 font-sans text-[9px] leading-none text-muted-foreground">
                {sitting.termCode.replace('-', "'")}
              </span>
            )}
          </span>
        )
      })}
    </div>
  )
}
