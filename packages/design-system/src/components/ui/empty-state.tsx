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
        'flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center',
        className,
      )}
      {...props}
    >
      {icon ? (
        <div className="grid size-12 place-items-center rounded-full bg-secondary text-secondary-foreground [&_svg]:size-6">
          {icon}
        </div>
      ) : null}
      <h2 className="font-display text-lg font-bold">{title}</h2>
      {description ? <p className="max-w-md text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}
