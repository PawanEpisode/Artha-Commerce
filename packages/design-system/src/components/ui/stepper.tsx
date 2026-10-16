import * as React from 'react'

import { Check } from '../../icons'
import { cn } from '../../lib/utils'

interface StepperProps extends React.ComponentProps<'ol'> {
  steps: string[]
  /** Zero-based index of the current step. */
  current: number
  /** Makes every step a button, for flows where any step can be visited (editing). Without it the steps are plain text. */
  onStepSelect?: (index: number) => void
}

/** Progress through a short flow (onboarding). Done steps show a check; the current one is aria-current="step". */
export function Stepper({ steps, current, onStepSelect, className, ...props }: StepperProps) {
  return (
    <ol
      data-slot="stepper"
      aria-label="Progress"
      className={cn('flex items-center gap-2 text-[13px]', className)}
      {...props}
    >
      {steps.map((label, i) => {
        const done = i < current
        const active = i === current
        const marker = (
          <>
            <span
              aria-hidden
              className={cn(
                'grid size-6 shrink-0 place-items-center rounded-full border text-xs font-semibold',
                done && 'border-primary bg-primary text-primary-foreground',
                active && 'border-primary text-primary',
                !done && !active && 'border-input text-muted-foreground',
              )}
            >
              {done ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}
            </span>
            <span
              className={cn(
                // On phones only the numbered dots show (a clipped label helps nobody); the text stays for screen readers.
                'truncate max-sm:sr-only',
                active ? 'font-semibold' : 'text-muted-foreground',
              )}
            >
              {label}
              {done ? <span className="sr-only"> (done)</span> : null}
            </span>
          </>
        )
        return (
          <li key={label} aria-current={active ? 'step' : undefined} className="flex min-w-0 flex-1 items-center gap-2">
            {onStepSelect ? (
              <button
                type="button"
                onClick={() => onStepSelect(i)}
                className="-m-1.5 flex min-h-8 min-w-0 cursor-pointer items-center gap-2 rounded-md p-1.5 outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 pointer-coarse:min-h-11"
              >
                {marker}
              </button>
            ) : (
              marker
            )}
            {i < steps.length - 1 ? <span aria-hidden className="h-px flex-1 bg-border" /> : null}
          </li>
        )
      })}
    </ol>
  )
}
