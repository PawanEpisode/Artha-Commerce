import * as React from 'react'

import { cn } from '../../lib/utils'

/**
 * Dense data table (`DataTable`) for the app: 36 px rows, hairline separators, quiet header. Use it instead of a stack of cards whenever
 * the items share the same fields (questions, papers, sets, notes, cards, sessions). The wrapper scrolls on its own, so a
 * wide table never widens the page. Give the clickable row a real link in its first cell (`TableLink`).
 */
export function DataTable({
  className,
  containerClassName,
  ...props
}: React.ComponentProps<'table'> & { containerClassName?: string }) {
  return (
    <div
      data-slot="table-container"
      className={cn('relative w-full overflow-x-auto rounded-lg border bg-card', containerClassName)}
    >
      <table data-slot="table" className={cn('w-full caption-bottom text-[13px]', className)} {...props} />
    </div>
  )
}

export function TableHeader({ className, ...props }: React.ComponentProps<'thead'>) {
  return (
    <thead data-slot="table-header" className={cn('border-b bg-muted/60 [&_tr]:border-b-0', className)} {...props} />
  )
}

export function TableBody({ className, ...props }: React.ComponentProps<'tbody'>) {
  return <tbody data-slot="table-body" className={cn('[&_tr:last-child]:border-0', className)} {...props} />
}

export function TableRow({ className, ...props }: React.ComponentProps<'tr'>) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        'border-b transition-colors focus-within:bg-muted/50 hover:bg-muted/50 data-[state=selected]:bg-muted motion-reduce:transition-none',
        className,
      )}
      {...props}
    />
  )
}

export function TableHead({ className, ...props }: React.ComponentProps<'th'>) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        'h-8 px-3 text-left align-middle text-[11px] font-medium tracking-wide whitespace-nowrap text-muted-foreground uppercase first:pl-3.5 last:pr-3.5',
        className,
      )}
      {...props}
    />
  )
}

export function TableCell({ className, ...props }: React.ComponentProps<'td'>) {
  return (
    <td
      data-slot="table-cell"
      className={cn('h-9 px-3 py-1.5 align-middle first:pl-3.5 last:pr-3.5', className)}
      {...props}
    />
  )
}

export function TableCaption({ className, ...props }: React.ComponentProps<'caption'>) {
  return <caption className={cn('mt-2 mb-2 text-xs text-muted-foreground', className)} {...props} />
}

/** The toolbar row above a table: search and filters on the left, view actions on the right. */
export function TableToolbar({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="table-toolbar"
      className={cn('flex flex-wrap items-center gap-2 [&>[data-slot=input]]:w-56', className)}
      {...props}
    />
  )
}
