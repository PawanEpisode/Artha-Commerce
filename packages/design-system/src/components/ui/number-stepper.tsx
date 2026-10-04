import { cn } from '../../lib/utils'
import { Button } from './button'

interface NumberStepperProps {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  /** Accessible name, e.g. "Chapters read". */
  label: string
  className?: string
  disabled?: boolean
}

/** − / + control with a live value. 44px targets; value is a spinbutton for assistive tech. */
export function NumberStepper({
  value,
  onChange,
  min = 0,
  max = 999,
  step = 1,
  label,
  className,
  disabled,
}: NumberStepperProps) {
  const set = (n: number) => onChange(Math.min(max, Math.max(min, n)))
  return (
    <div
      data-slot="number-stepper"
      role="group"
      aria-label={label}
      className={cn('inline-flex items-center gap-2', className)}
    >
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-11"
        aria-label={`Decrease ${label}`}
        disabled={disabled || value <= min}
        onClick={() => set(value - step)}
      >
        <span aria-hidden className="text-lg leading-none">
          −
        </span>
      </Button>
      <span
        role="spinbutton"
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={min}
        aria-valuemax={max}
        className="min-w-10 text-center text-lg font-semibold tabular-nums"
      >
        {value}
      </span>
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-11"
        aria-label={`Increase ${label}`}
        disabled={disabled || value >= max}
        onClick={() => set(value + step)}
      >
        <span aria-hidden className="text-lg leading-none">
          +
        </span>
      </Button>
    </div>
  )
}
