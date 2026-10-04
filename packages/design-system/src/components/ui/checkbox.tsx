import { Checkbox as CheckboxPrimitive } from 'radix-ui'
import * as React from 'react'

import { Check } from '../../icons'
import { cn } from '../../lib/utils'

/**
 * Visually 24px, with a 44px hit area (pseudo element), so it is easy to tap in a long list.
 * The check mark is an icon, so the checked state is not colour only.
 */
export function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        'relative grid size-6 shrink-0 place-items-center rounded-md border-2 border-input bg-card text-primary-foreground transition-colors outline-none before:absolute before:-inset-2.5 before:content-[""] focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-primary data-[state=checked]:bg-primary',
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator>
        <Check className="size-4" strokeWidth={3} />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}
