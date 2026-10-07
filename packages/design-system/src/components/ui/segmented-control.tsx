import { RadioGroup as RadioGroupPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'

interface SegmentedControlProps<T extends string> extends Omit<
  React.ComponentProps<typeof RadioGroupPrimitive.Root>,
  'value' | 'onValueChange' | 'children' | 'defaultValue'
> {
  value: T
  onValueChange: (value: T) => void
  options: ReadonlyArray<{
    value: T
    /** Also the accessible name when the label is hidden. */
    label: string
    /** A decorative icon (from `@artha/design-system`) shown before the label. */
    icon?: React.ReactNode
  }>
  /** Accessible name of the group. */
  label: string
  /** Stretch the choices across the full width, with a 44px target. */
  stretch?: boolean
  /** `lg` makes every choice at least 44 px tall and wide (tool pickers on touch screens). */
  size?: 'md' | 'lg'
  /** Show only the icons from small screens down; the label stays as the accessible name and returns from `sm` up. */
  iconOnlyOnMobile?: boolean
}

/**
 * One choice out of a few, shown as a row of buttons. A radio group underneath, so arrow keys move the choice. With
 * `icon` on the options it is also the one-active-tool pill (select, highlight, pen): the choice is shown by the raised
 * surface and the group is announced as "1 of N", never by colour alone.
 */
export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  label,
  stretch = false,
  size = 'md',
  iconOnlyOnMobile = false,
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
      className={cn(
        'inline-flex flex-wrap items-center gap-1 rounded-xl bg-muted p-1',
        stretch && 'flex w-full flex-nowrap',
        className,
      )}
      {...props}
    >
      {options.map((o) => (
        <RadioGroupPrimitive.Item
          key={o.value}
          value={o.value}
          className={cn(
            'inline-flex h-9 min-w-11 items-center justify-center rounded-lg px-3 text-sm font-semibold text-muted-foreground transition-all outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 data-[state=checked]:bg-card data-[state=checked]:text-foreground data-[state=checked]:shadow-soft',
            size === 'lg' && 'h-11 min-w-11',
            stretch && 'h-11 min-w-0 flex-1 basis-0 px-1',
            o.icon ? 'gap-2 [&_svg]:size-4 [&_svg]:shrink-0' : null,
          )}
        >
          {o.icon}
          <span className={cn(iconOnlyOnMobile && o.icon && 'sr-only sm:not-sr-only')}>{o.label}</span>
        </RadioGroupPrimitive.Item>
      ))}
    </RadioGroupPrimitive.Root>
  )
}
