import * as React from 'react'

import { ChevronRight } from '../../icons'
import { cn } from '../../lib/utils'

export function Breadcrumb({ className, ...props }: React.ComponentProps<'nav'>) {
  return <nav data-slot="breadcrumb" aria-label="Breadcrumb" className={className} {...props} />
}

export function BreadcrumbList({ className, ...props }: React.ComponentProps<'ol'>) {
  return (
    <ol className={cn('flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground', className)} {...props} />
  )
}

export function BreadcrumbItem({ className, ...props }: React.ComponentProps<'li'>) {
  return <li className={cn('inline-flex items-center gap-1.5', className)} {...props} />
}

export function BreadcrumbSeparator() {
  return <ChevronRight className="size-3.5" aria-hidden />
}

/** The current page: not a link, announced as current. */
export function BreadcrumbPage({ className, ...props }: React.ComponentProps<'span'>) {
  return <span aria-current="page" className={cn('font-semibold text-foreground', className)} {...props} />
}
