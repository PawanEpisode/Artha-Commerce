import * as React from 'react'

import { cn } from '../../lib/utils'

/** Loading placeholder. Decorative: wrap a group in an element with aria-busy and an sr-only status. */
export function Skeleton({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden
      className={cn('animate-pulse rounded-lg bg-secondary motion-reduce:animate-none', className)}
      {...props}
    />
  )
}
