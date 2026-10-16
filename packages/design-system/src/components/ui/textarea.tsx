import * as React from 'react'

import { cn } from '../../lib/utils'

export function Textarea({ className, ...props }: React.ComponentProps<'textarea'>) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        'flex min-h-20 w-full rounded-md border border-input bg-card px-2.5 py-2 text-[13px] transition-shadow outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/50 disabled:opacity-50 aria-invalid:border-destructive pointer-coarse:text-base',
        className,
      )}
      {...props}
    />
  )
}
