import * as React from 'react'

import { cn } from '../../lib/utils'

export interface MarksBarProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number
  max?: number
  sharePct?: number
  label?: string
  showValueText?: boolean
  formatValue?: (val: number) => string
}

/**
 * Horizontal marks / share indicator with accessible tabular numbers.
 * Reference: PRD 7.4.
 */
export function MarksBar({
  value,
  max = 100,
  sharePct,
  label,
  showValueText = true,
  formatValue = (v) => `${v.toFixed(1)}m`,
  className,
  ...props
}: MarksBarProps) {
  const percentage = Math.max(0, Math.min(100, sharePct !== undefined ? sharePct : (value / (max || 1)) * 100))

  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label || `${value} marks out of ${max}`}
      className={cn('flex w-full flex-col gap-1', className)}
      {...props}
    >
      <div className="flex items-center justify-between font-mono text-xs tabular-nums">
        {label && <span className="font-sans text-muted-foreground">{label}</span>}
        {showValueText && (
          <span className="ml-auto font-semibold text-foreground">
            {formatValue(value)}
            {sharePct !== undefined && (
              <span className="ml-1 font-sans font-normal text-muted-foreground">({sharePct.toFixed(1)}%)</span>
            )}
          </span>
        )}
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted/60">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}
