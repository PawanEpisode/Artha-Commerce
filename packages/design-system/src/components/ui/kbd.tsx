import * as React from 'react'

import { cn } from '../../lib/utils'

/** A keyboard key in running text ("Press Space to pause"). */
export function Kbd({ className, ...props }: React.ComponentProps<'kbd'>) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        'inline-flex min-w-5 items-center justify-center rounded border border-border bg-secondary px-1 py-px font-mono text-[11px] font-medium text-secondary-foreground',
        className,
      )}
      {...props}
    />
  )
}
