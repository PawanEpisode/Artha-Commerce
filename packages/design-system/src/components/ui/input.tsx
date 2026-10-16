import * as React from 'react'

import { cn } from '../../lib/utils'

export function Input({ className, type, ...props }: React.ComponentProps<'input'>) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        'flex h-8 w-full min-w-0 rounded-md border border-input bg-card px-2.5 text-[13px] transition-shadow outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:focus-visible:ring-destructive/30 pointer-coarse:h-11 pointer-coarse:text-base',
        className,
      )}
      {...props}
    />
  )
}
