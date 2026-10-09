import * as React from 'react'

import { BookOpen, Check, LoaderCircle } from '../../icons'
import { cn } from '../../lib/utils'

export interface ReadToggleProps extends Omit<React.ComponentProps<'button'>, 'onChange' | 'children' | 'value'> {
  checked: boolean
  onChange: (next: boolean) => void
  /** A save is in flight: shows a spinner, blocks repeat clicks, keeps the optimistic state visible. */
  pending?: boolean
  /** Labels, so a screen can say "Mark chapter as read". */
  labels?: { unchecked: string; checked: string }
}

/**
 * "Mark as read" control. aria-pressed toggle that swaps its icon to a tick and its label to "Read".
 * The visible label always matches the accessible name, and the tick pops in unless motion is reduced.
 */
export function ReadToggle({
  checked,
  onChange,
  pending = false,
  labels = { unchecked: 'Mark as read', checked: 'Read' },
  disabled,
  className,
  ...props
}: ReadToggleProps) {
  return (
    <button
      type="button"
      data-slot="read-toggle"
      aria-pressed={checked}
      aria-busy={pending || undefined}
      disabled={disabled}
      onClick={() => {
        if (!pending) onChange(!checked)
      }}
      className={cn(
        'inline-flex min-h-11 shrink-0 cursor-pointer items-center gap-2 rounded-full border px-4 text-sm font-semibold whitespace-nowrap transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 active:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-busy:cursor-progress motion-reduce:transition-none motion-reduce:active:translate-y-0',
        checked
          ? 'border-success-border bg-success-bg text-success-fg hover:brightness-95'
          : 'border-input bg-card text-foreground hover:bg-muted',
        className,
      )}
      {...props}
    >
      <span className="relative grid size-5 place-items-center" aria-hidden>
        {pending ? (
          <LoaderCircle className="size-5 animate-spin motion-reduce:animate-none" />
        ) : checked ? (
          <Check key="on" className="size-5 animate-in duration-200 zoom-in-50 motion-reduce:animate-none" />
        ) : (
          <BookOpen key="off" className="size-5 animate-in duration-150 fade-in motion-reduce:animate-none" />
        )}
      </span>
      <span>{checked ? labels.checked : labels.unchecked}</span>
    </button>
  )
}
