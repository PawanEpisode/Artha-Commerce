import React from 'react'

import { formatRemaining } from '../lib/attempt-machine'

interface CountdownTimerProps {
  remainingMs: number
  label?: string
  warningThresholdMs?: number
  className?: string
}

export const CountdownTimer: React.FC<CountdownTimerProps> = ({
  remainingMs,
  label = 'Time Remaining',
  warningThresholdMs = 300_000, // 5 mins
  className = '',
}) => {
  const isUrgent = remainingMs > 0 && remainingMs <= warningThresholdMs
  const formatted = formatRemaining(remainingMs)

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 font-mono text-sm font-medium transition-colors ${
        isUrgent
          ? 'animate-pulse border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300'
          : 'border-border bg-muted/40 text-foreground'
      } ${className}`}
      role="timer"
      aria-label={`${label}: ${formatted}`}
      aria-live={isUrgent ? 'assertive' : 'off'}
    >
      <svg
        className={`h-4 w-4 ${isUrgent ? 'text-rose-600 dark:text-rose-400' : 'text-muted-foreground'}`}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <span>{formatted}</span>
    </div>
  )
}
