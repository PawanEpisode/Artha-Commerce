import * as React from 'react'

import { X } from '../../icons'
import { cn } from '../../lib/utils'

export interface TagInputProps {
  value: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
  maxTags?: number
  disabled?: boolean
  className?: string
  'aria-label'?: string
  id?: string
}

export function TagInput({
  value = [],
  onChange,
  placeholder = 'Add a tag...',
  maxTags,
  disabled = false,
  className,
  'aria-label': ariaLabel = 'Tags',
  id,
}: TagInputProps) {
  const [inputValue, setInputValue] = React.useState('')
  const inputRef = React.useRef<HTMLInputElement>(null)

  const handleAdd = (tag: string) => {
    const trimmed = tag.trim().replace(/^,+|,+$/g, '')
    if (!trimmed) return
    if (value.includes(trimmed)) {
      setInputValue('')
      return
    }
    if (maxTags !== undefined && value.length >= maxTags) return
    onChange([...value, trimmed])
    setInputValue('')
  }

  const handleRemove = (indexToRemove: number) => {
    if (disabled) return
    onChange(value.filter((_, idx) => idx !== indexToRemove))
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      handleAdd(inputValue)
    } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
      e.preventDefault()
      handleRemove(value.length - 1)
    }
  }

  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        'flex min-h-11 w-full flex-wrap items-center gap-1.5 rounded-lg border border-input bg-card p-1.5 text-sm transition-colors focus-within:ring-[3px] focus-within:ring-ring/40',
        disabled && 'cursor-not-allowed opacity-50',
        className,
      )}
    >
      {value.map((tag, idx) => (
        <span
          key={`${tag}-${idx}`}
          className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-xs font-medium text-foreground"
        >
          <span className="max-w-40 truncate">{tag}</span>
          {!disabled && (
            <button
              type="button"
              aria-label={`Remove tag ${tag}`}
              onClick={(e) => {
                e.stopPropagation()
                handleRemove(idx)
              }}
              className="grid size-4 place-items-center rounded-sm text-muted-foreground hover:bg-background/80 hover:text-foreground"
            >
              <X aria-hidden className="size-3" />
            </button>
          )}
        </span>
      ))}
      {(!maxTags || value.length < maxTags) && !disabled && (
        <input
          ref={inputRef}
          id={id}
          type="text"
          value={inputValue}
          disabled={disabled}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (inputValue.trim()) handleAdd(inputValue)
          }}
          placeholder={value.length === 0 ? placeholder : ''}
          className="min-w-24 flex-1 bg-transparent px-1.5 py-1 text-sm outline-none placeholder:text-muted-foreground"
        />
      )}
    </div>
  )
}
