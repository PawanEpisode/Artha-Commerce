import { Checkbox as CheckboxPrimitive } from 'radix-ui'
import * as React from 'react'

import { Check } from '../../icons'
import { cn } from '../../lib/utils'

/**
 * Visually 16px, with a 44px hit area on touch (pseudo element), so it is easy to tap in a long list.
 * The check mark is an icon, so the checked state is not colour only.
 */
export function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        'relative grid size-4 shrink-0 cursor-pointer place-items-center rounded-sm border border-input bg-card text-primary-foreground transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-primary data-[state=checked]:bg-primary pointer-coarse:before:absolute pointer-coarse:before:-inset-3.5 pointer-coarse:before:content-[""]',
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator>
        <Check className="size-3" strokeWidth={3} />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}
