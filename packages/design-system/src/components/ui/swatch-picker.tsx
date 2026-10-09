import { cva } from 'class-variance-authority'
import { RadioGroup as RadioGroupPrimitive } from 'radix-ui'
import * as React from 'react'

import { Check } from '../../icons'
import { cn } from '../../lib/utils'

/** Markup colour keys: `y g b p o` are highlight colours, `i1` to `i5` are pen colours. The API stores these keys. */
export const HIGHLIGHT_SWATCH_KEYS = ['y', 'g', 'b', 'p', 'o'] as const
export const INK_SWATCH_KEYS = ['i1', 'i2', 'i3', 'i4', 'i5'] as const
export type SwatchKey = (typeof HIGHLIGHT_SWATCH_KEYS)[number] | (typeof INK_SWATCH_KEYS)[number]

export interface SwatchOption {
  key: SwatchKey
  /** The accessible name, from the student's own legend ("Formula or rule"). Never the colour word alone. */
  name: string
  disabled?: boolean
}

/**
 * Class names are written out in full so Tailwind can see them. Highlights are a fill with a stronger edge; pens are a
 * solid disc in the pen colour. The marker colour is chosen per family to keep 4.5:1 on the fill (check:contrast).
 */
const LOOK: Record<SwatchKey, string> = {
  y: 'border-highlight-yellow-edge bg-highlight-yellow text-swatch-marker',
  g: 'border-highlight-green-edge bg-highlight-green text-swatch-marker',
  b: 'border-highlight-blue-edge bg-highlight-blue text-swatch-marker',
  p: 'border-highlight-pink-edge bg-highlight-pink text-swatch-marker',
  o: 'border-highlight-orange-edge bg-highlight-orange text-swatch-marker',
  i1: 'border-ink-1 bg-ink-1 text-swatch-marker-inverse',
  i2: 'border-ink-2 bg-ink-2 text-swatch-marker-inverse',
  i3: 'border-ink-3 bg-ink-3 text-swatch-marker-inverse',
  i4: 'border-ink-4 bg-ink-4 text-swatch-marker-inverse',
  i5: 'border-ink-5 bg-ink-5 text-swatch-marker-inverse',
}

/** A distinct shape per colour, so the choice works without seeing colour. Solid for highlights, outlined for pens. */
const SHAPES: Record<SwatchKey, React.ReactElement> = {
  y: <circle cx="12" cy="12" r="6" />,
  g: <rect x="6.5" y="6.5" width="11" height="11" />,
  b: <path d="M12 5.5 19 18H5Z" />,
  p: <path d="M12 4 20 12 12 20 4 12Z" />,
  o: <path d="M12 3.5 14.6 9l6 .8-4.4 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.4 9.8l6-.8Z" />,
  i1: <circle cx="12" cy="12" r="6" />,
  i2: <rect x="6.5" y="6.5" width="11" height="11" />,
  i3: <path d="M12 5.5 19 18H5Z" />,
  i4: <path d="M12 4 20 12 12 20 4 12Z" />,
  i5: <path d="M12 3.5 14.6 9l6 .8-4.4 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.4 9.8l6-.8Z" />,
}

const isInk = (key: SwatchKey) => key.startsWith('i')

/** The shape that goes with a colour (circle, square, triangle, diamond, star), for marks drawn on a page so the colour is never the only signal. */
export function SwatchShape({ swatch, className }: { swatch: SwatchKey; className?: string }) {
  const outlined = isInk(swatch)
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      data-shape={swatch}
      className={cn('size-full', className)}
      fill={outlined ? 'none' : 'currentColor'}
      stroke="currentColor"
      strokeWidth={outlined ? 2.5 : 1}
      strokeLinejoin="round"
    >
      {SHAPES[swatch]}
    </svg>
  )
}

const chipVariants = cva(
  'relative grid shrink-0 place-items-center rounded-full border-2 transition-shadow group-data-[state=checked]/swatch:ring-2 group-data-[state=checked]/swatch:ring-foreground group-data-[state=checked]/swatch:ring-offset-2 group-data-[state=checked]/swatch:ring-offset-background motion-reduce:transition-none',
  {
    variants: {
      size: {
        sm: 'size-6 p-1',
        md: 'size-8 p-1.5',
        lg: 'size-10 p-2',
      },
    },
    defaultVariants: { size: 'md' },
  },
)

export interface SwatchPickerProps extends Omit<
  React.ComponentProps<typeof RadioGroupPrimitive.Root>,
  'children' | 'onSelect' | 'dir' | 'orientation'
> {
  /** Accessible name of the group ("Highlight colour", "Pen colour"). */
  label: string
  options: ReadonlyArray<SwatchOption>
  /** Visual size of the swatch. The tap target stays at least 44 px for every size. */
  size?: 'sm' | 'md' | 'lg'
  /** Show each name beside its swatch (legend editors, menus). Otherwise the name is the accessible name only. */
  showNames?: boolean
  /** Fires on every choice, including tapping the colour that is already selected (apply it again). */
  onSelect?: (key: SwatchKey) => void
  onValueChange?: (key: SwatchKey) => void
  value?: SwatchKey | null
  defaultValue?: SwatchKey
}

/**
 * A radio group of markup colours. Each swatch has an accessible name, a shape that is unique within the family, a 44 px
 * target and a selected state that adds a check mark and a ring (never colour alone). Arrow keys move the choice
 * (roving tabindex, from Radix RadioGroup). Wrap the picker in the app with the student's legend names.
 */
export function SwatchPicker({
  label,
  options,
  size = 'md',
  showNames = false,
  onSelect,
  onValueChange,
  value,
  defaultValue,
  className,
  ...props
}: SwatchPickerProps) {
  return (
    <RadioGroupPrimitive.Root
      data-slot="swatch-picker"
      aria-label={label}
      loop
      value={value === undefined ? undefined : (value ?? '')}
      defaultValue={defaultValue}
      onValueChange={(v) => onValueChange?.(v as SwatchKey)}
      className={cn('flex flex-wrap items-center', showNames ? 'gap-2' : 'gap-0.5', className)}
      {...props}
    >
      {options.map((option) => (
        <RadioGroupPrimitive.Item
          key={option.key}
          value={option.key}
          disabled={option.disabled}
          aria-label={showNames ? undefined : option.name}
          title={showNames ? undefined : option.name}
          onClick={() => onSelect?.(option.key)}
          data-slot="swatch"
          data-swatch={option.key}
          className={cn(
            'group/swatch relative inline-flex min-h-11 max-w-full min-w-11 cursor-pointer items-center justify-center gap-2 rounded-xl text-left text-sm font-medium outline-none focus-visible:ring-[3px] focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50',
            showNames && 'justify-start border border-input bg-card py-1 ps-2 pe-3 hover:bg-muted',
            showNames && 'data-[state=checked]:border-foreground data-[state=checked]:bg-secondary',
          )}
        >
          <span className={cn(chipVariants({ size }), LOOK[option.key])}>
            <SwatchShape swatch={option.key} />
            <RadioGroupPrimitive.Indicator
              aria-hidden
              className="absolute -end-1.5 -top-1.5 grid size-4 place-items-center rounded-full bg-foreground text-background"
            >
              <Check className="size-3" strokeWidth={3} />
            </RadioGroupPrimitive.Indicator>
          </span>
          {showNames ? <span className="min-w-0 break-words">{option.name}</span> : null}
        </RadioGroupPrimitive.Item>
      ))}
    </RadioGroupPrimitive.Root>
  )
}
