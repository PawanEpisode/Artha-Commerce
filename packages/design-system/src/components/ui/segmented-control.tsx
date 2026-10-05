import { RadioGroup as RadioGroupPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'

interface SegmentedControlProps<T extends string> extends Omit<
  React.ComponentProps<typeof RadioGroupPrimitive.Root>,
  'value' | 'onValueChange' | 'children' | 'defaultValue'
> {
  value: T
  onValueChange: (value: T) => void
  options: ReadonlyArray<{ value: T; label: string }>
  /** Accessible name of the group. */
  label: string
}

/** One choice out of a few, shown as a row of buttons. A radio group underneath, so arrow keys move the choice. */
export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  label,
  className,
  ...props
}: SegmentedControlProps<T>) {
  return (
    <RadioGroupPrimitive.Root
      data-slot="segmented-control"
      aria-label={label}
      value={value}
      onValueChange={(v) => onValueChange(v as T)}
      orientation="horizontal"
      className={cn('inline-flex flex-wrap items-center gap-1 rounded-xl bg-muted p-1', className)}
      {...props}
    >
      {options.map((o) => (
        <RadioGroupPrimitive.Item
          key={o.value}
          value={o.value}
          className="inline-flex h-9 min-w-11 items-center justify-center rounded-lg px-3 text-sm font-semibold text-muted-foreground transition-all outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 data-[state=checked]:bg-card data-[state=checked]:text-foreground data-[state=checked]:shadow-soft"
        >
          {o.label}
        </RadioGroupPrimitive.Item>
      ))}
    </RadioGroupPrimitive.Root>
  )
}
