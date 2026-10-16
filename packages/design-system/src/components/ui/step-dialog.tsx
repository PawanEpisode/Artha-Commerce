import * as React from 'react'

import { cn } from '../../lib/utils'
import { Button } from './button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './dialog'
import { Stepper } from './stepper'

export interface StepDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The flow's name: "Upload a PDF". */
  title: string
  description?: React.ReactNode
  /** Labels of the steps, in order. A single step shows no progress. */
  steps: ReadonlyArray<string>
  /** Zero-based index of the current step. */
  current: number
  /** Makes the progress markers buttons, for flows where any step can be visited (editing). */
  onStepSelect?: (index: number) => void
  /** Heading of the current step; it takes focus when the step changes. */
  stepTitle: string
  stepDescription?: React.ReactNode
  /** The current step's fields. This area scrolls; the header and the footer stay in view. */
  children: React.ReactNode
  /** Footer, left side: Skip, Move to Trash. */
  aside?: React.ReactNode
  /** Shows a Back button before the primary action. */
  onBack?: () => void
  backLabel?: string
  /** The primary action (a Button): Next on the early steps, the finishing action on the last. */
  action?: React.ReactNode
  className?: string
}

/**
 * A modal that walks through a short flow in steps (upload, edit details). One heading per step, progress that screen
 * readers announce, Back and a primary action pinned at the bottom, and a body that scrolls on its own so the actions never
 * leave the screen on a phone. Focus moves to the step heading when the step changes.
 */
export function StepDialog({
  open,
  onOpenChange,
  title,
  description,
  steps,
  current,
  onStepSelect,
  stepTitle,
  stepDescription,
  children,
  aside,
  onBack,
  backLabel = 'Back',
  action,
  className,
}: StepDialogProps) {
  const heading = React.useRef<HTMLHeadingElement>(null)
  const first = React.useRef(true)
  const index = Math.min(current, Math.max(steps.length - 1, 0))

  React.useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    heading.current?.focus()
  }, [current, stepTitle])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-slot="step-dialog"
        className={cn(
          'flex max-h-[min(92dvh,46rem)] w-[min(36rem,calc(100vw-1rem))] flex-col gap-0 overflow-hidden p-0',
          className,
        )}
      >
        <div className="space-y-3 border-b border-border px-4 pt-4 pb-3 sm:px-5 sm:pt-5">
          <div>
            <DialogTitle>{title}</DialogTitle>
            {description ? (
              <DialogDescription className="break-words">{description}</DialogDescription>
            ) : (
              <DialogDescription className="sr-only">{title}</DialogDescription>
            )}
          </div>
          {steps.length > 1 ? (
            <>
              <Stepper steps={[...steps]} current={index} onStepSelect={onStepSelect} />
              <p className="sr-only" role="status">
                Step {index + 1} of {steps.length}: {stepTitle}
              </p>
            </>
          ) : null}
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4 sm:px-5">
          <div className="space-y-1">
            <h3 ref={heading} tabIndex={-1} className="text-base font-semibold outline-none">
              {stepTitle}
            </h3>
            {stepDescription ? <p className="text-[13px] text-muted-foreground">{stepDescription}</p> : null}
          </div>
          {children}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-5">
          <div className="flex min-w-0 flex-wrap items-center gap-2">{aside}</div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {onBack ? (
              <Button type="button" variant="ghost" onClick={onBack}>
                {backLabel}
              </Button>
            ) : null}
            {action}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
