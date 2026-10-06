import { TextField } from '@artha/design-system'
import { useEffect, useRef } from 'react'

import { isValidTime } from '../lib/quietHours'

const COMMIT_DELAY_MS = 800

/**
 * A time input that saves as the student settles: when they leave the field, or a moment after the last change
 * (a phone's time picker never blurs). The parent owns the draft value; `onCommit` only fires for a valid time.
 */
export function TimeField({
  id,
  label,
  value,
  onValueChange,
  onCommit,
  hint,
  error,
  disabled,
}: {
  id: string
  label: string
  value: string
  onValueChange: (value: string) => void
  onCommit: (value: string) => void
  hint?: string
  error?: string
  disabled?: boolean
}) {
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const commit = (next: string) => {
    window.clearTimeout(timer.current)
    if (isValidTime(next)) onCommit(next)
  }

  return (
    <TextField
      id={id}
      type="time"
      label={label}
      value={value}
      hint={hint}
      error={error}
      disabled={disabled}
      onChange={(event) => {
        const next = event.target.value
        onValueChange(next)
        window.clearTimeout(timer.current)
        timer.current = window.setTimeout(() => commit(next), COMMIT_DELAY_MS)
      }}
      onBlur={(event) => commit(event.target.value)}
    />
  )
}
