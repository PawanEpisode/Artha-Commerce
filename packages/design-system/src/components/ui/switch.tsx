import { Switch as SwitchPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'

export function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-input bg-card transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-primary data-[state=checked]:bg-primary pointer-coarse:before:absolute pointer-coarse:before:-inset-3 pointer-coarse:before:content-[""]',
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="block size-3 translate-x-0.5 rounded-full bg-input shadow transition-transform data-[state=checked]:translate-x-4.5 data-[state=checked]:bg-primary-foreground motion-reduce:transition-none" />
    </SwitchPrimitive.Root>
  )
}
