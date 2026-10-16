import * as React from 'react'

import { Check, ChevronDown, Search, X } from '../../icons'
import { cn } from '../../lib/utils'
import { Popover, PopoverContent, PopoverTrigger } from './popover'

export interface ComboboxOption {
  value: string
  label: string
  badge?: string
  disabled?: boolean
}

export interface ComboboxProps {
  options: ComboboxOption[]
  value?: string | string[]
  onChange?: (value: string | string[]) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  disabled?: boolean
  multiple?: boolean
  className?: string
  triggerClassName?: string
  'aria-label'?: string
  id?: string
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder = 'Select option...',
  searchPlaceholder = 'Search...',
  emptyText = 'No options found.',
  disabled = false,
  multiple = false,
  className,
  triggerClassName,
  'aria-label': ariaLabel,
  id,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false)
  const [search, setSearch] = React.useState('')
  const [highlightedIndex, setHighlightedIndex] = React.useState(0)
  const inputRef = React.useRef<HTMLInputElement>(null)

  const selectedValues = React.useMemo(() => {
    if (value === undefined || value === null) return []
    return Array.isArray(value) ? value : [value]
  }, [value])

  const filteredOptions = React.useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return options
    return options.filter((opt) => opt.label.toLowerCase().includes(q) || opt.value.toLowerCase().includes(q))
  }, [options, search])

  React.useEffect(() => {
    if (open) {
      setSearch('')
      setHighlightedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const handleSelect = (optValue: string) => {
    if (!onChange) return
    if (multiple) {
      const next = selectedValues.includes(optValue)
        ? selectedValues.filter((v) => v !== optValue)
        : [...selectedValues, optValue]
      onChange(next)
    } else {
      onChange(optValue)
      setOpen(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightedIndex((prev) => (prev + 1 < filteredOptions.length ? prev + 1 : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightedIndex((prev) => (prev - 1 >= 0 ? prev - 1 : filteredOptions.length - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const opt = filteredOptions[highlightedIndex]
      if (opt && !opt.disabled) {
        handleSelect(opt.value)
      }
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const triggerLabel = React.useMemo(() => {
    if (selectedValues.length === 0) return placeholder
    if (multiple) {
      if (selectedValues.length === 1) {
        const found = options.find((o) => o.value === selectedValues[0])
        return found ? found.label : selectedValues[0]
      }
      return `${selectedValues.length} selected`
    }
    const found = options.find((o) => o.value === selectedValues[0])
    return found ? found.label : placeholder
  }, [selectedValues, options, multiple, placeholder])

  const listboxId = React.useId()

  return (
    <div className={cn('relative inline-block w-full', className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            id={id}
            type="button"
            disabled={disabled}
            aria-expanded={open}
            aria-label={ariaLabel ?? placeholder}
            className={cn(
              'flex h-8 w-full cursor-pointer items-center justify-between gap-2 rounded-md border border-input bg-card px-2.5 text-left text-[13px] transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 pointer-coarse:h-11 pointer-coarse:text-base',
              selectedValues.length === 0 && 'text-muted-foreground',
              triggerClassName,
            )}
          >
            <span className="truncate">{triggerLabel}</span>
            <ChevronDown aria-hidden className="size-4 shrink-0 text-muted-foreground" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-[min(26rem,calc(100vw-2rem))] p-0" align="start" onKeyDown={handleKeyDown}>
          <div className="flex items-center border-b border-border px-2.5 py-1.5">
            <Search aria-hidden className="mr-2 size-3.5 shrink-0 text-muted-foreground" />
            <input
              ref={inputRef}
              type="text"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={open}
              aria-controls={listboxId}
              placeholder={searchPlaceholder}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setHighlightedIndex(0)
              }}
              className="w-full bg-transparent text-[13px] outline-none placeholder:text-muted-foreground pointer-coarse:text-base"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="rounded-sm p-0.5 text-muted-foreground hover:text-foreground pointer-coarse:p-2"
                aria-label="Clear search"
              >
                <X aria-hidden className="size-3.5" />
              </button>
            )}
          </div>
          <div
            id={listboxId}
            role="listbox"
            aria-multiselectable={multiple}
            className="max-h-60 overflow-y-auto p-1 text-[13px]"
          >
            {filteredOptions.length === 0 ? (
              <div className="py-3 text-center text-[13px] text-muted-foreground">{emptyText}</div>
            ) : (
              filteredOptions.map((opt, index) => {
                const isSelected = selectedValues.includes(opt.value)
                const isHighlighted = index === highlightedIndex
                return (
                  <button
                    key={opt.value}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    disabled={opt.disabled}
                    onClick={() => handleSelect(opt.value)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={cn(
                      'flex w-full cursor-pointer items-center justify-between rounded-md px-2 py-1.5 text-left text-[13px] transition-colors outline-none pointer-coarse:min-h-11',
                      isHighlighted && 'bg-accent text-accent-foreground',
                      isSelected && 'font-medium',
                      opt.disabled && 'cursor-not-allowed opacity-50',
                    )}
                  >
                    <div className="flex items-center gap-2 truncate">
                      {multiple && (
                        <div
                          className={cn(
                            'flex size-4 shrink-0 items-center justify-center rounded border border-border',
                            isSelected && 'border-primary bg-primary text-primary-foreground',
                          )}
                        >
                          {isSelected && <Check aria-hidden className="size-3 stroke-[3]" />}
                        </div>
                      )}
                      <span className="truncate">{opt.label}</span>
                      {opt.badge && (
                        <span className="rounded-sm bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                          {opt.badge}
                        </span>
                      )}
                    </div>
                    {!multiple && isSelected && <Check aria-hidden className="size-4 shrink-0 text-primary" />}
                  </button>
                )
              })
            )}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}
