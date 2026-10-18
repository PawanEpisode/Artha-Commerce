import * as React from 'react'

import { Check, CircleAlert, Info, TriangleAlert } from '../../icons'
import { cn } from '../../lib/utils'

export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'insufficient'

interface LevelConfig {
  label: string
  description: string
  cls: string
  Icon: typeof Check
}

const CONFIG: Record<ConfidenceLevel, LevelConfig> = {
  high: {
    label: 'High confidence',
    description: 'Based on 6+ sittings with stable pattern',
    cls: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800',
    Icon: Check,
  },
  medium: {
    label: 'Medium confidence',
    description: 'Based on 4-5 sittings or carries older sittings',
    cls: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800',
    Icon: Info,
  },
  low: {
    label: 'Low confidence',
    description: 'Based on only 3 past exam sittings',
    cls: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800',
    Icon: TriangleAlert,
  },
  insufficient: {
    label: 'Insufficient data',
    description: 'Fewer than 3 sittings available',
    cls: 'bg-muted text-muted-foreground border-border',
    Icon: CircleAlert,
  },
}

export interface ConfidenceBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  level: ConfidenceLevel
  showIcon?: boolean
  onClick?: () => void
}

/**
 * Visual badge indicating statistical confidence of recommendations.
 * Opens explanation sheet or tooltip on click.
 * Reference: PRD 7.4.
 */
export function ConfidenceBadge({ level, showIcon = true, onClick, className, ...props }: ConfidenceBadgeProps) {
  const meta = CONFIG[level] || CONFIG.insufficient
  const { label, description, cls, Icon } = meta

  return (
    <span
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onClick()
              }
            }
          : undefined
      }
      title={description}
      aria-label={`${label}: ${description}`}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium transition-colors select-none',
        cls,
        onClick &&
          'cursor-pointer hover:opacity-85 focus:ring-2 focus:ring-ring focus:ring-offset-1 focus:outline-none',
        className,
      )}
      {...props}
    >
      {showIcon && <Icon className="size-3 shrink-0" strokeWidth={2.5} aria-hidden />}
      <span>{label}</span>
    </span>
  )
}
