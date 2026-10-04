import { RadioGroup as RadioGroupPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'

export function RadioGroup({ className, ...props }: React.ComponentProps<typeof RadioGroupPrimitive.Root>) {
  return <RadioGroupPrimitive.Root data-slot="radio-group" className={cn('grid gap-3', className)} {...props} />
}

/** A selectable card: whole surface is the click target (44px+), with a clear checked state that is not colour only. */
export function RadioCardItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      data-slot="radio-card-item"
      className={cn(
        'group flex min-h-16 w-full items-start gap-3 rounded-xl border border-input bg-card p-4 text-left transition-colors outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40 data-[state=checked]:border-primary data-[state=checked]:bg-secondary',
        className,
      )}
      {...props}
    >
      <span
        aria-hidden
        className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border-2 border-input group-data-[state=checked]:border-primary"
      >
        <RadioGroupPrimitive.Indicator className="size-2.5 rounded-full bg-primary" />
      </span>
      <span className="min-w-0 flex-1">{children}</span>
    </RadioGroupPrimitive.Item>
  )
}
