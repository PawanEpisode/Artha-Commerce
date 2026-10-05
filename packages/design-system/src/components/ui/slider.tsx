import { Slider as SliderPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'

interface SliderProps extends Omit<React.ComponentProps<typeof SliderPrimitive.Root>, 'value' | 'onValueChange'> {
  value: number
  onValueChange: (value: number) => void
  /** Accessible name, e.g. "Alert volume". */
  label: string
}

/** One-handle slider. Arrow keys step, Home and End jump; the thumb is a 44px target and keeps a visible focus ring. */
export function Slider({ value, onValueChange, label, className, ...props }: SliderProps) {
  return (
    <SliderPrimitive.Root
      data-slot="slider"
      value={[value]}
      onValueChange={([v]) => onValueChange(v ?? value)}
      className={cn('relative flex h-11 w-full touch-none items-center select-none', className)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-2 grow overflow-hidden rounded-full bg-secondary">
        <SliderPrimitive.Range className="absolute h-full bg-primary" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        aria-label={label}
        className="block size-6 rounded-full border-2 border-primary bg-card shadow outline-none before:absolute before:-inset-3 before:content-[''] focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:opacity-50"
      />
    </SliderPrimitive.Root>
  )
}
