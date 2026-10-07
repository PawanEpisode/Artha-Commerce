import { cva } from 'class-variance-authority'
import * as React from 'react'

import { CircleCheck, CloudOff, LoaderCircle, TriangleAlert } from '../../icons'
import { cn } from '../../lib/utils'

export type SyncState = 'saved' | 'saving' | 'offline' | 'attention'

const chipVariants = cva(
  'inline-flex min-h-8 items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold [&_svg]:size-3.5 [&_svg]:shrink-0',
  {
    variants: {
      state: {
        saved: 'border-success-border bg-success-bg text-success-fg',
        saving: 'border-border bg-muted text-muted-foreground',
        offline: 'border-info-border bg-info-bg text-info-fg',
        attention: 'border-warning-border bg-warning-bg text-warning-fg',
      },
    },
  },
)

/** The words for each state. Exported so a screen can show the same sentence somewhere else (a banner, a title). */
export function syncChipText(state: SyncState, count = 0): string {
  switch (state) {
    case 'saved':
      return 'Saved'
    case 'saving':
      return 'Saving…'
    case 'offline':
      return count > 0 ? `Offline: saved on this device, ${count} waiting` : 'Offline: saved on this device'
    case 'attention':
      return count === 1 ? '1 needs your attention' : `${count || 1} need your attention`
  }
}

const ICONS = { saved: CircleCheck, saving: LoaderCircle, offline: CloudOff, attention: TriangleAlert } as const

interface SyncChipProps extends Omit<React.ComponentProps<'span'>, 'children' | 'onClick'> {
  state: SyncState
  /** Entries waiting (offline) or conflicts to settle (attention). */
  count?: number
  /** When given, the chip is a button (for example to open the conflict sheet). Only useful for `attention`. */
  onPress?: () => void
}

/**
 * Save status: Saved, Saving, Offline with a count, Needs attention. Icon plus words, never colour alone. It is a live
 * region (`aria-live="polite"`), so a change of state is announced without moving focus.
 */
export function SyncChip({ state, count, onPress, className, ...props }: SyncChipProps) {
  const Icon = ICONS[state]
  const text = syncChipText(state, count)
  const content = (
    <>
      <Icon aria-hidden className={cn(state === 'saving' && 'animate-spin motion-reduce:animate-none')} />
      <span>{text}</span>
    </>
  )
  return (
    <span data-slot="sync-chip" data-state={state} role="status" aria-live="polite" className="inline-flex">
      {onPress ? (
        <button
          type="button"
          onClick={onPress}
          className={cn(
            chipVariants({ state }),
            'min-h-11 cursor-pointer px-4 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40',
            className,
          )}
        >
          {content}
        </button>
      ) : (
        <span className={cn(chipVariants({ state }), className)} {...props}>
          {content}
        </span>
      )}
    </span>
  )
}
