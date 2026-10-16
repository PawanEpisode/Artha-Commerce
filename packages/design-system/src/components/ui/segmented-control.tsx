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
  /** Stretch the choices across the full width. */
  stretch?: boolean
  /** `lg` makes every choice at least 44 px tall and wide (tool pickers on touch screens). `md` is 24 px, 36 px on touch. */
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
        'inline-flex flex-wrap items-center gap-1 rounded-lg bg-muted p-0.5',
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
            'inline-flex h-6 min-w-8 cursor-pointer items-center justify-center rounded-md px-2.5 text-xs font-medium text-muted-foreground transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50 data-[state=checked]:bg-card data-[state=checked]:text-foreground data-[state=checked]:shadow-soft pointer-coarse:h-9 pointer-coarse:min-w-11',
            size === 'lg' && 'h-11 min-w-11',
            stretch && 'min-w-0 flex-1 basis-0 px-1 pointer-coarse:h-11',
            o.icon ? 'gap-1.5 [&_svg]:size-3.5 [&_svg]:shrink-0' : null,
          )}
        >
          {o.icon}
          <span className={cn(iconOnlyOnMobile && o.icon && 'sr-only sm:not-sr-only')}>{o.label}</span>
        </RadioGroupPrimitive.Item>
      ))}
    </RadioGroupPrimitive.Root>
  )
}
