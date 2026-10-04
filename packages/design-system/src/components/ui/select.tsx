import * as React from 'react'

import { ChevronDown } from '../../icons'
import { cn } from '../../lib/utils'

/** Native select: best mobile UX and accessibility for short lists. Pair with Label via htmlFor/id. */
export function Select({ className, children, ...props }: React.ComponentProps<'select'>) {
  return (
    <div className="relative">
      <select
        data-slot="select"
        className={cn(
          'h-11 w-full appearance-none rounded-lg border border-input bg-card pr-10 pl-3.5 text-base outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:opacity-50 aria-invalid:border-destructive md:text-sm',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
    </div>
  )
}
