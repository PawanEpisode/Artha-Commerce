import { Dialog as DialogPrimitive } from 'radix-ui'
import * as React from 'react'

import { CornerDownLeft, type LucideIcon, Search } from '../../icons'
import { cn } from '../../lib/utils'
import { Kbd } from './kbd'

export interface CommandItem {
  id: string
  label: string
  group?: string
  icon?: LucideIcon
  /** Extra words that should find this item. */
  keywords?: readonly string[]
  /** Right-aligned hint, e.g. a shortcut. */
  hint?: string
}

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  items: readonly CommandItem[]
  onSelect: (item: CommandItem) => void
  placeholder?: string
}

const MAX_RESULTS = 40

/** Tokens must all appear, in any order, in the label, group or keywords. */
export function filterCommands(items: readonly CommandItem[], query: string): CommandItem[] {
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (tokens.length === 0) return items.slice(0, MAX_RESULTS)
  return items
    .filter((item) => {
      const hay = [item.label, item.group ?? '', ...(item.keywords ?? [])].join(' ').toLowerCase()
      return tokens.every((t) => hay.includes(t))
    })
    .slice(0, MAX_RESULTS)
}

/** Jump-to palette (Cmd/Ctrl+K). A combobox over a listbox: arrows move, Enter picks, Escape closes. */
export function CommandPalette({
  open,
  onOpenChange,
  items,
  onSelect,
  placeholder = 'Search or jump to…',
}: CommandPaletteProps) {
  const [query, setQuery] = React.useState('')
  const [active, setActive] = React.useState(0)
  const listId = React.useId()
  const results = React.useMemo(() => filterCommands(items, query), [items, query])

  React.useEffect(() => {
    if (!open) {
      setQuery('')
      setActive(0)
    }
  }, [open])
  React.useEffect(() => setActive(0), [query])
  React.useEffect(() => {
    document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: 'nearest' })
  }, [active, listId])

  const choose = (item: CommandItem | undefined) => {
    if (!item) return
    onOpenChange(false)
    onSelect(item)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => Math.min(results.length - 1, i + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(0, i - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      choose(results[active])
    }
  }

  let lastGroup: string | undefined
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-foreground/30 data-[state=open]:animate-in data-[state=open]:fade-in-0 motion-reduce:animate-none" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed top-[12vh] left-1/2 z-50 w-[min(34rem,calc(100vw-1.5rem))] -translate-x-1/2 overflow-hidden rounded-xl border bg-popover text-[13px] text-popover-foreground shadow-lift outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 motion-reduce:animate-none"
        >
          <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
          <div className="flex items-center gap-2 border-b px-3">
            <Search aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            <input
              role="combobox"
              aria-expanded
              aria-controls={listId}
              aria-activedescendant={results.length ? `${listId}-${active}` : undefined}
              aria-label="Search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={placeholder}
              className="h-11 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <ul id={listId} role="listbox" aria-label="Results" className="max-h-[min(22rem,60dvh)] overflow-y-auto p-1">
            {results.length === 0 ? (
              <li className="px-3 py-6 text-center text-muted-foreground">Nothing matches “{query}”.</li>
            ) : null}
            {results.map((item, i) => {
              const showGroup = item.group && item.group !== lastGroup
              lastGroup = item.group
              const Icon = item.icon
              return (
                <React.Fragment key={item.id}>
                  {showGroup ? (
                    <li
                      role="presentation"
                      className="px-2.5 pt-2 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase"
                    >
                      {item.group}
                    </li>
                  ) : null}
                  {/* Keyboard use goes through the combobox input above (arrows and Enter), so the option needs no key handler. */}
                  {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
                  <li
                    id={`${listId}-${i}`}
                    role="option"
                    aria-selected={i === active}
                    onPointerMove={() => setActive(i)}
                    onClick={() => choose(item)}
                    className={cn(
                      'flex h-8 cursor-pointer items-center gap-2.5 rounded-md px-2.5',
                      i === active && 'bg-muted',
                    )}
                  >
                    {Icon ? <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" /> : null}
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    {item.hint ? <Kbd>{item.hint}</Kbd> : null}
                    {i === active ? <CornerDownLeft aria-hidden className="size-3.5 text-muted-foreground" /> : null}
                  </li>
                </React.Fragment>
              )
            })}
          </ul>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
