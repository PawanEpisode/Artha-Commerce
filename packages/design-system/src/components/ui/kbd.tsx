import * as React from 'react'

import { cn } from '../../lib/utils'

/** A keyboard key in running text ("Press Space to pause"). */
export function Kbd({ className, ...props }: React.ComponentProps<'kbd'>) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        'inline-flex min-w-6 items-center justify-center rounded-md border border-border bg-secondary px-1.5 py-0.5 font-mono text-xs font-semibold text-secondary-foreground',
        className,
      )}
      {...props}
    />
  )
}
