import * as React from 'react'

import { Check } from '../../icons'
import { cn } from '../../lib/utils'

interface StepperProps extends React.ComponentProps<'ol'> {
  steps: string[]
  /** Zero-based index of the current step. */
  current: number
}

/** Progress through a short flow (onboarding). Done steps show a check; the current one is aria-current="step". */
export function Stepper({ steps, current, className, ...props }: StepperProps) {
  return (
    <ol
      data-slot="stepper"
      aria-label="Progress"
      className={cn('flex items-center gap-2 text-sm', className)}
      {...props}
    >
      {steps.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <li key={label} aria-current={active ? 'step' : undefined} className="flex min-w-0 flex-1 items-center gap-2">
            <span
              aria-hidden
              className={cn(
                'grid size-7 shrink-0 place-items-center rounded-full border-2 text-xs font-bold',
                done && 'border-primary bg-primary text-primary-foreground',
                active && 'border-primary text-primary',
                !done && !active && 'border-input text-muted-foreground',
              )}
            >
              {done ? <Check className="size-4" strokeWidth={3} /> : i + 1}
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
            {i < steps.length - 1 ? <span aria-hidden className="h-0.5 flex-1 rounded bg-border" /> : null}
          </li>
        )
      })}
    </ol>
  )
}
