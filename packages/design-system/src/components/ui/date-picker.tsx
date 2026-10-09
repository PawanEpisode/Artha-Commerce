import * as React from 'react'

import { cn } from '../../lib/utils'
import { Input } from './input'
import { Label } from './label'

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/

/** True for a real calendar day written `YYYY-MM-DD` (rejects `2026-02-30`). */
export function isIsoDate(value: string): boolean {
  const m = ISO.exec(value)
  if (!m) return false
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const date = new Date(Date.UTC(y, mo - 1, d))
  return date.getUTCFullYear() === y && date.getUTCMonth() === mo - 1 && date.getUTCDate() === d
}

/** Keep `value` between `min` and `max` (either may be missing). ISO dates sort as text, so no time zone enters into it. */
export function clampIsoDate(value: string, min?: string, max?: string): string {
  if (min && value < min) return min
  if (max && value > max) return max
  return value
}

/** The ISO date `days` after `from` (negative for before), in plain calendar arithmetic. */
export function addIsoDays(from: string, days: number): string {
  const m = ISO.exec(from)
  if (!m) return from
  const date = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + days))
  return date.toISOString().slice(0, 10)
}

/** Today in the browser's own calendar as `YYYY-MM-DD` (not UTC: a student at 00:30 in India is on the new day). */
export function todayIsoDate(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

interface DatePickerProps extends Omit<React.ComponentProps<'input'>, 'type' | 'value' | 'onChange' | 'min' | 'max'> {
  /** `YYYY-MM-DD`, or '' / null for no date. */
  value: string | null
  /** Called with a valid `YYYY-MM-DD` (already kept within `min` and `max`), or null when the field is cleared. */
  onValueChange: (value: string | null) => void
  label: string
  min?: string
  max?: string
  hint?: string
  /** Validation message from the caller. Announced and sets aria-invalid. */
  error?: string
}

/**
 * A date field on the browser's own date input, so phones show their native picker and keyboards type the day directly.
 * Labelled, with a hint and an error wired for screen readers, and a 44 px target. Used for the vacation end date; the exam
 * date comes in R2. The browser does not always enforce `min` and `max` when a date is typed, so the value is clamped here.
 */
export function DatePicker({
  id: idProp,
  value,
  onValueChange,
  label,
  min,
  max,
  hint,
  error,
  className,
  ...props
}: DatePickerProps) {
  const generated = React.useId()
  const id = idProp ?? generated
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined
  return (
    <div data-slot="date-picker" className={cn('grid gap-2', className)}>
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="date"
        value={value ?? ''}
        min={min}
        max={max}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        onChange={(e) => {
          const raw = e.target.value
          if (!raw) return onValueChange(null)
          if (isIsoDate(raw)) onValueChange(clampIsoDate(raw, min, max))
        }}
        {...props}
      />
      {hint ? (
        <p id={hintId} className="text-sm text-muted-foreground">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}
