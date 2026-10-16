import * as React from 'react'

import { cn } from '../../lib/utils'

interface EmptyStateProps extends Omit<React.ComponentProps<'div'>, 'title'> {
  icon?: React.ReactNode
  title: React.ReactNode
  description?: React.ReactNode
  /** Usually a Button. */
  action?: React.ReactNode
}

export function EmptyState({ icon, title, description, action, className, ...props }: EmptyStateProps) {
  return (
    <div
      data-slot="empty-state"
      className={cn(
        'flex flex-col items-center gap-2 rounded-lg border border-dashed border-border bg-card px-4 py-8 text-center',
        className,
      )}
      {...props}
    >
      {icon ? (
        <div className="grid size-9 place-items-center rounded-md bg-secondary text-secondary-foreground [&_svg]:size-5">
          {icon}
        </div>
      ) : null}
      <h2 className="text-sm font-semibold">{title}</h2>
      {description ? <p className="max-w-md text-[13px] text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  )
}
