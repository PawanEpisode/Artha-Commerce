import { cn } from '../../lib/utils'

export interface PresetChipOption<T extends string> {
  value: T
  label: string
  /** Short second line, e.g. "2 · 2 · 2". */
  description?: string
}

interface PresetChipsProps<T extends string> {
  options: ReadonlyArray<PresetChipOption<T>>
  /** The chosen preset, or null when the values match none of them (a custom setting). */
  value: T | null
  onValueChange: (value: T) => void
  /** Accessible name of the group. */
  label: string
  disabled?: boolean
  className?: string
}

/**
 * A few named starting points for a group of numbers (Light, Standard, Intense). Buttons with a pressed state, not a
 * radio group, because "none selected" is a valid state: the numbers below may be custom. Checked state shows a mark
 * and a border, never colour alone.
 */
export function PresetChips<T extends string>({
  options,
  value,
  onValueChange,
  label,
  disabled,
  className,
}: PresetChipsProps<T>) {
  return (
    <div role="group" aria-label={label} data-slot="preset-chips" className={cn('grid grid-cols-3 gap-1.5', className)}>
      {options.map((o) => {
        const pressed = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={pressed}
            disabled={disabled}
            onClick={() => onValueChange(o.value)}
            className={cn(
              'flex min-h-12 cursor-pointer flex-col items-start gap-0.5 rounded-lg border border-input bg-card p-2.5 text-left transition-colors outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50',
              pressed && 'border-primary bg-secondary',
            )}
          >
            <span className="flex items-center gap-1.5 text-[13px] font-semibold">
              {o.label}
              {pressed ? (
                <span aria-hidden className="text-primary">
                  ✓
                </span>
              ) : null}
            </span>
            {o.description ? <span className="text-xs text-muted-foreground tabular-nums">{o.description}</span> : null}
          </button>
        )
      })}
    </div>
  )
}
