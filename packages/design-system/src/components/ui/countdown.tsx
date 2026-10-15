import * as React from 'react'

import { Clock, Pause, TriangleAlert } from '../../icons'
import { cn } from '../../lib/utils'

export interface CountdownProps {
  /** Seconds remaining in the countdown. */
  secondsRemaining: number
  /** True when the session timer is paused. */
  isPaused?: boolean
  /** Seconds threshold for warning level (default 300 = 5m). */
  warningThreshold?: number
  /** Seconds threshold for critical danger level (default 60 = 1m). */
  dangerThreshold?: number
  /** Optional callback fired when secondsRemaining reaches 0. */
  onExpire?: () => void
  /** Size variant. */
  size?: 'sm' | 'md' | 'lg'
  /** Whether to render a leading icon. */
  showIcon?: boolean
  className?: string
}

export function formatCountdownTime(totalSeconds: number): string {
  if (totalSeconds <= 0) return '00:00'
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  const pad = (n: number) => n.toString().padStart(2, '0')

  if (hours > 0) {
    return `${hours}:${pad(minutes)}:${pad(seconds)}`
  }
  return `${pad(minutes)}:${pad(seconds)}`
}

export function Countdown({
  secondsRemaining,
  isPaused = false,
  warningThreshold = 300,
  dangerThreshold = 60,
  onExpire,
  size = 'md',
  showIcon = true,
  className,
}: CountdownProps) {
  const isExpired = secondsRemaining <= 0
  const isDanger = !isExpired && secondsRemaining <= dangerThreshold
  const isWarning = !isExpired && !isDanger && secondsRemaining <= warningThreshold

  React.useEffect(() => {
    if (isExpired && onExpire) {
      onExpire()
    }
  }, [isExpired, onExpire])

  const formatted = formatCountdownTime(secondsRemaining)
  const minutesLeft = Math.ceil(secondsRemaining / 60)
  const spokenLabel = isPaused
    ? 'Timer paused'
    : isExpired
      ? 'Time is up'
      : `${minutesLeft} ${minutesLeft === 1 ? 'minute' : 'minutes'} remaining`

  return (
    <div
      role="timer"
      aria-live="polite"
      aria-label={spokenLabel}
      className={cn(
        'inline-flex items-center gap-1.5 font-mono tabular-nums transition-colors',
        size === 'sm' && 'text-xs',
        size === 'md' && 'text-sm font-semibold',
        size === 'lg' && 'text-base font-bold',
        isPaused && 'text-muted-foreground italic',
        !isPaused && !isWarning && !isDanger && 'text-foreground',
        isWarning && 'text-amber-600 dark:text-amber-400',
        isDanger && 'animate-pulse font-bold text-destructive',
        className,
      )}
    >
      {showIcon && (
        <>
          {isPaused ? (
            <Pause aria-hidden className="size-4 shrink-0" />
          ) : isDanger ? (
            <TriangleAlert aria-hidden className="size-4 shrink-0 animate-bounce" />
          ) : (
            <Clock aria-hidden className="size-4 shrink-0" />
          )}
        </>
      )}
      <span>{isExpired ? '00:00' : formatted}</span>
      {isPaused && <span className="text-xs font-normal text-muted-foreground not-italic">(Paused)</span>}
    </div>
  )
}
