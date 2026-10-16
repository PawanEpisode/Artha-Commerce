import * as React from 'react'

import { X } from '../../icons'
import { cn } from '../../lib/utils'

interface FilterChipProps extends Omit<React.ComponentProps<'span'>, 'children'> {
  /** What the chip filters on: "Tag: doubt". Shown as text. */
  children: React.ReactNode
  /** Accessible name of the remove button, for example "Remove filter Tag: doubt". */
  removeLabel: string
  onRemove: () => void
}

/** An active filter shown as a removable chip. The remove button is 24px, 44px on touch; the chip is not colour only. */
export function FilterChip({ children, removeLabel, onRemove, className, ...props }: FilterChipProps) {
  return (
    <span
      data-slot="filter-chip"
      className={cn(
        'inline-flex max-w-full items-center gap-0.5 rounded-md border border-border bg-card py-0.5 pr-0.5 pl-2 text-xs font-medium',
        className,
      )}
      {...props}
    >
      <span className="min-w-0 truncate">{children}</span>
      <button
        type="button"
        aria-label={removeLabel}
        onClick={onRemove}
        className="grid size-6 shrink-0 cursor-pointer place-items-center rounded-sm text-muted-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 pointer-coarse:size-11"
      >
        <X aria-hidden className="size-3" />
      </button>
    </span>
  )
}
