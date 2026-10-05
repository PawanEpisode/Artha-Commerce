import * as React from 'react'

import { clampMinutes, joinMinutes, parseDurationPart, splitMinutes } from '../../lib/duration'
import { cn } from '../../lib/utils'
import { Input } from './input'
import { Label } from './label'

export interface DurationFieldProps {
  /** Total minutes, or null when empty. */
  valueMinutes: number | null
  onChangeMinutes: (minutes: number | null) => void
  /** Visible legend, e.g. "Daily goal". */
  label: string
  hint?: string
  error?: string
  /** Upper bound in minutes; larger input is clamped. Default 24 h. */
  maxMinutes?: number
  /** Arrow up/down step for the minutes box. Default 5. */
  stepMinutes?: number
  size?: 'default' | 'compact'
  disabled?: boolean
  required?: boolean
  id?: string
  className?: string
}

const toText = (n: number | null | undefined) => (n === null || n === undefined ? '' : String(n))

/**
 * Hours + minutes inputs for a duration that the app stores as whole minutes.
 * Typing is free-form (75 in Minutes is accepted as you type); on blur it normalises to 1 h 15 m.
 */
export function DurationField({
  valueMinutes,
  onChangeMinutes,
  label,
  hint,
  error,
  maxMinutes = 24 * 60,
  stepMinutes = 5,
  size = 'default',
  disabled,
  required,
  id: idProp,
  className,
}: DurationFieldProps) {
  const generated = React.useId()
  const id = idProp ?? generated
  const legendId = `${id}-legend`
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined

  const initial = valueMinutes === null ? null : splitMinutes(valueMinutes)
  const [hours, setHours] = React.useState(toText(initial?.hours))
  const [minutes, setMinutes] = React.useState(toText(initial?.minutes))
  const lastEmitted = React.useRef<number | null>(valueMinutes)

  // Follow outside changes (reset, loaded data) but never overwrite what is being typed.
  React.useEffect(() => {
    if (valueMinutes === lastEmitted.current) return
    lastEmitted.current = valueMinutes
    const parts = valueMinutes === null ? null : splitMinutes(valueMinutes)
    setHours(toText(parts?.hours))
    setMinutes(toText(parts?.minutes))
  }, [valueMinutes])

  const emit = (h: string, m: string) => {
    const hp = parseDurationPart(h)
    const mp = parseDurationPart(m)
    const next = hp === null && mp === null ? null : clampMinutes(joinMinutes(hp ?? 0, mp ?? 0), maxMinutes)
    lastEmitted.current = next
    onChangeMinutes(next)
  }

  const normalise = () => {
    const hp = parseDurationPart(hours)
    const mp = parseDurationPart(minutes)
    if (hp === null && mp === null) {
      setHours('')
      setMinutes('')
      return
    }
    const total = clampMinutes(joinMinutes(hp ?? 0, mp ?? 0), maxMinutes)
    const parts = splitMinutes(total)
    setHours(String(parts.hours))
    setMinutes(String(parts.minutes))
    if (total !== lastEmitted.current) {
      lastEmitted.current = total
      onChangeMinutes(total)
    }
  }

  const bump = (which: 'h' | 'm') => (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    event.preventDefault()
    const dir = event.key === 'ArrowUp' ? 1 : -1
    const current = joinMinutes(parseDurationPart(hours) ?? 0, parseDurationPart(minutes) ?? 0)
    const delta = which === 'h' ? 60 : stepMinutes
    const total = clampMinutes(current + dir * delta, maxMinutes)
    const parts = splitMinutes(total)
    setHours(String(parts.hours))
    setMinutes(String(parts.minutes))
    lastEmitted.current = total
    onChangeMinutes(total)
  }

  const compact = size === 'compact'
  const inputClass = cn('text-center tabular-nums', compact ? 'h-11 w-20 md:text-base' : 'h-12 w-24 text-lg md:text-lg')

  return (
    <div
      role="group"
      aria-labelledby={legendId}
      aria-describedby={describedBy}
      data-slot="duration-field"
      className={cn('grid gap-2', className)}
    >
      <span id={legendId} className="text-sm leading-none font-semibold">
        {label}
        {required ? <span aria-hidden> *</span> : null}
      </span>
      <div className="flex items-end gap-3">
        <div className="grid gap-1">
          <Label htmlFor={`${id}-h`} className="text-xs font-medium text-muted-foreground">
            Hours
          </Label>
          <Input
            id={`${id}-h`}
            inputMode="numeric"
            autoComplete="off"
            placeholder="0"
            value={hours}
            disabled={disabled}
            required={required}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={inputClass}
            onChange={(e) => {
              const v = e.target.value.replace(/\D/g, '').slice(0, 3)
              setHours(v)
              emit(v, minutes)
            }}
            onKeyDown={bump('h')}
            onBlur={normalise}
          />
        </div>
        <span aria-hidden className="pb-3 text-lg font-semibold text-muted-foreground">
          :
        </span>
        <div className="grid gap-1">
          <Label htmlFor={`${id}-m`} className="text-xs font-medium text-muted-foreground">
            Minutes
          </Label>
          <Input
            id={`${id}-m`}
            inputMode="numeric"
            autoComplete="off"
            placeholder="0"
            value={minutes}
            disabled={disabled}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={inputClass}
            onChange={(e) => {
              const v = e.target.value.replace(/\D/g, '').slice(0, 4)
              setMinutes(v)
              emit(hours, v)
            }}
            onKeyDown={bump('m')}
            onBlur={normalise}
          />
        </div>
      </div>
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
