import * as React from 'react'

import { ArrowLeft } from '../../icons'
import { cn } from '../../lib/utils'
import { Button } from './button'
import { Stepper } from './stepper'

export interface StepFlowProps {
  /** Labels of the steps this student will walk, in order. */
  steps: ReadonlyArray<string>
  /** Zero-based index of the current step. */
  current: number
  title: string
  description?: string
  /** Shown as a Back button above the title when set. */
  onBack?: () => void
  children?: React.ReactNode
  className?: string
}

/**
 * The frame of a multi-step flow (onboarding): progress, one heading per step, Back. When the step changes, focus moves
 * to the heading and "Step 2 of 5" is announced, so keyboard and screen reader users never lose their place.
 */
export function StepFlow({ steps, current, title, description, onBack, children, className }: StepFlowProps) {
  const heading = React.useRef<HTMLHeadingElement>(null)
  const first = React.useRef(true)

  React.useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    heading.current?.focus()
  }, [current, title])

  return (
    <section data-slot="step-flow" className={cn('space-y-8', className)}>
      <div className="space-y-4">
        <Stepper steps={[...steps]} current={Math.min(current, steps.length - 1)} />
        <p className="sr-only" role="status">
          Step {Math.min(current + 1, steps.length)} of {steps.length}: {title}
        </p>
      </div>
      <div className="space-y-2">
        {onBack ? (
          <Button type="button" variant="ghost" size="sm" className="-ml-3" onClick={onBack}>
            <ArrowLeft aria-hidden /> Back
          </Button>
        ) : null}
        <h1 ref={heading} tabIndex={-1} className="font-display text-3xl font-extrabold outline-none">
          {title}
        </h1>
        {description ? <p className="text-muted-foreground">{description}</p> : null}
      </div>
      {children}
    </section>
  )
}
