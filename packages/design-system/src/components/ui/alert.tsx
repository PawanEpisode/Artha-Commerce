import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'

import { CircleAlert, CircleCheck, Info } from '../../icons'
import { cn } from '../../lib/utils'

const alertVariants = cva('flex items-start gap-3 rounded-xl border p-4 text-sm text-foreground', {
  variants: {
    variant: {
      info: 'border-input bg-secondary',
      success: 'border-accent bg-accent/15',
      error: 'border-destructive bg-destructive/10',
    },
  },
  defaultVariants: { variant: 'info' },
})

const icons = { info: Info, success: CircleCheck, error: CircleAlert } as const
const iconColour = { info: 'text-primary', success: 'text-foreground', error: 'text-destructive' } as const

/** Inline message. Errors use role="alert" (interrupts), the rest role="status" (polite). Icon plus text, never colour only. */
export function Alert({
  variant = 'info',
  className,
  children,
  ...props
}: React.ComponentProps<'div'> & VariantProps<typeof alertVariants>) {
  const kind = variant ?? 'info'
  const Icon = icons[kind]
  return (
    <div
      data-slot="alert"
      role={kind === 'error' ? 'alert' : 'status'}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    >
      <Icon aria-hidden className={cn('mt-0.5 size-4 shrink-0', iconColour[kind])} />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
