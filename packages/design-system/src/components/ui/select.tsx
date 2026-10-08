import { Select as SelectPrimitive } from 'radix-ui'
import * as React from 'react'

import { Check, ChevronDown, LoaderCircle } from '../../icons'
import { cn } from '../../lib/utils'

/**
 * Radix rejects an empty item value. Call sites that mean "nothing" keep passing `""`; this maps it inside the menu.
 */
const EMPTY = '__empty__'
const toItem = (value: string) => (value === '' ? EMPTY : value)
const fromItem = (value: string) => (value === EMPTY ? '' : value)

export const Select = SelectPrimitive.Root
export const SelectGroup = SelectPrimitive.Group
export const SelectValue = SelectPrimitive.Value

export function SelectTrigger({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      className={cn(
        'flex h-11 w-full items-center justify-between gap-2 rounded-lg border border-input bg-card px-3.5 text-left text-base outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm [&_svg]:pointer-events-none [&_svg]:shrink-0 [&>span]:line-clamp-1',
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDown className="size-4 text-muted-foreground" aria-hidden />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  )
}

export function SelectContent({
  className,
  children,
  position = 'popper',
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        data-slot="select-content"
        position={position}
        sideOffset={6}
        collisionPadding={12}
        className={cn(
          'z-[60] max-h-72 min-w-(--radix-select-trigger-width) overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-lift data-[state=open]:animate-in data-[state=open]:fade-in-0 motion-reduce:animate-none',
          className,
        )}
        {...props}
      >
        <SelectPrimitive.Viewport className="max-h-72 overflow-y-auto p-1">{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  )
}

export function SelectItem({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        'relative flex min-h-11 w-full cursor-default items-center rounded-lg py-2 pr-8 pl-3 text-sm outline-none select-none focus:bg-muted data-disabled:pointer-events-none data-disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <span className="absolute right-2 flex size-4 items-center justify-center">
        <SelectPrimitive.ItemIndicator>
          <Check className="size-4" aria-hidden />
        </SelectPrimitive.ItemIndicator>
      </span>
    </SelectPrimitive.Item>
  )
}

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

interface SelectFieldProps {
  id?: string
  value: string
  onValueChange: (value: string) => void
  options: readonly SelectOption[]
  placeholder?: string
  disabled?: boolean
  className?: string
  'aria-label'?: string
  /** The options are still being fetched: the open menu shows a spinner row instead of looking empty. */
  loading?: boolean
  loadingText?: string
  /** Shown in the open menu when there is nothing to choose besides the "none" entry. */
  emptyText?: string
}

/** A row of the open menu that says what is going on (loading, nothing to choose). Not selectable. */
function SelectStatus({ loading, children }: { loading?: boolean; children: React.ReactNode }) {
  return (
    <div
      data-slot="select-status"
      role="status"
      aria-live="polite"
      className="flex min-h-11 items-center gap-2 px-3 py-2 text-sm text-muted-foreground"
    >
      {loading ? <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" aria-hidden /> : null}
      {children}
    </div>
  )
}

/**
 * A labelled list of choices. `value` and `onValueChange` replace the native select's `value` and `onChange`.
 * An option value of `""` is allowed and means "none".
 */
export function SelectField({
  id,
  value,
  onValueChange,
  options,
  placeholder,
  disabled,
  className,
  'aria-label': ariaLabel,
  loading = false,
  loadingText = 'Loading…',
  emptyText = 'No options available',
}: SelectFieldProps) {
  const choices = options.filter((option) => option.value !== '').length
  const blank = options.find((option) => option.value === '')
  return (
    <Select value={toItem(value)} onValueChange={(next) => onValueChange(fromItem(next))} disabled={disabled}>
      <SelectTrigger id={id} className={className} aria-label={ariaLabel}>
        <SelectValue placeholder={placeholder ?? blank?.label} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value || EMPTY} value={toItem(option.value)} disabled={option.disabled}>
            {option.label}
          </SelectItem>
        ))}
        {loading ? <SelectStatus loading>{loadingText}</SelectStatus> : null}
        {!loading && choices === 0 ? <SelectStatus>{emptyText}</SelectStatus> : null}
      </SelectContent>
    </Select>
  )
}
