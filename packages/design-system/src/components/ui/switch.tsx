import { Switch as SwitchPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'

export function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        'relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full border-2 border-input bg-card transition-colors outline-none before:absolute before:-inset-2 before:content-[""] focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-primary data-[state=checked]:bg-primary',
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="block size-4 translate-x-1 rounded-full bg-input shadow transition-transform data-[state=checked]:translate-x-6 data-[state=checked]:bg-primary-foreground motion-reduce:transition-none" />
    </SwitchPrimitive.Root>
  )
}
