import * as React from 'react'

import type { LucideIcon } from '../../icons'
import { cn } from '../../lib/utils'

export interface SectionTabItem {
  value: string
  label: string
  icon?: LucideIcon
  /** Link tabs: where it goes. Panel tabs (variant="tablist") leave it out. */
  href?: string
  /** Panel tabs: id of the panel this tab controls (aria-controls). */
  controls?: string
  disabled?: boolean
}

export interface SectionTabLinkProps {
  className: string
  'aria-current'?: 'page'
  'data-active': boolean
  'data-tab': ''
  children: React.ReactNode
  onKeyDown: React.KeyboardEventHandler<HTMLElement>
}

export interface SectionTabsProps {
  /** Accessible name of the bar, e.g. "Tracker sections". */
  label: string
  items: ReadonlyArray<SectionTabItem>
  /** The active item's value. */
  value: string
  /** `nav` (default) is a list of links with aria-current="page". `tablist` switches in-page panels. */
  variant?: 'nav' | 'tablist'
  /** Called when a tablist tab is chosen. */
  onValueChange?: (value: string) => void
  /**
   * Render a link tab with your router: `(item, props) => <Link to={item.href} {...props} />`.
   * Spread `props` as given (className, aria-current, data-active, data-tab, onKeyDown). Falls back to a plain anchor.
   */
  renderLink?: (item: SectionTabItem, props: SectionTabLinkProps) => React.ReactNode
  /** Stick below the site header. Offset comes from `--site-header-height` (default 0). */
  sticky?: boolean
  className?: string
}

const tabClass =
  'relative inline-flex h-11 shrink-0 items-center gap-2 rounded-full px-4 text-base font-semibold whitespace-nowrap outline-none transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/40 motion-reduce:transition-none aria-disabled:pointer-events-none aria-disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0 data-[active=true]:bg-primary data-[active=true]:text-primary-foreground data-[active=true]:shadow-soft data-[active=false]:text-muted-foreground data-[active=false]:hover:bg-muted data-[active=false]:hover:text-foreground'

const scrollerClass =
  'relative overflow-x-auto overscroll-x-contain scroll-px-4 px-4 py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden'

/**
 * Sticky, horizontally scrollable sub-navigation with edge fades. The active tab scrolls into view,
 * arrow keys / Home / End move between tabs, and every tab is at least 44px tall with 16px text.
 */
export function SectionTabs({
  label,
  items,
  value,
  variant = 'nav',
  onValueChange,
  renderLink,
  sticky = true,
  className,
}: SectionTabsProps) {
  const scroller = React.useRef<HTMLDivElement>(null)
  const [edges, setEdges] = React.useState({ start: false, end: false })

  const measure = React.useCallback(() => {
    const el = scroller.current
    if (!el) return
    setEdges({ start: el.scrollLeft > 4, end: el.scrollLeft + el.clientWidth < el.scrollWidth - 4 })
  }, [])

  React.useEffect(() => {
    measure()
    const el = scroller.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [measure, items.length])

  // Keep the active tab visible: scroll the bar itself, never the page.
  React.useEffect(() => {
    const el = scroller.current
    const active = el?.querySelector<HTMLElement>('[data-active="true"]')
    if (!el || !active) return
    const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const left = active.offsetLeft - (el.clientWidth - active.offsetWidth) / 2
    el.scrollTo({ left: Math.max(0, left), behavior: reduce ? 'auto' : 'smooth' })
  }, [value])

  const onKeyDown: React.KeyboardEventHandler<HTMLElement> = (event) => {
    const keys = ['ArrowRight', 'ArrowLeft', 'Home', 'End']
    if (!keys.includes(event.key)) return
    const tabs = Array.from(
      scroller.current?.querySelectorAll<HTMLElement>('[data-tab]:not([aria-disabled="true"])') ?? [],
    )
    const index = tabs.indexOf(event.currentTarget as HTMLElement)
    if (index === -1) return
    event.preventDefault()
    const next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? tabs.length - 1
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
    tabs[next]?.focus()
    if (variant === 'tablist') tabs[next]?.click()
  }

  const content = (item: SectionTabItem) => {
    const Icon = item.icon
    return (
      <>
        {Icon ? <Icon aria-hidden /> : null}
        {item.label}
      </>
    )
  }

  return (
    <div
      data-slot="section-tabs"
      className={cn(
        'z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85',
        sticky && 'sticky top-[var(--site-header-height,0px)]',
        className,
      )}
    >
      <div className="relative">
        {variant === 'nav' ? (
          <nav ref={scroller} aria-label={label} onScroll={measure} className={scrollerClass}>
            <ul className="flex gap-1">
              {items.map((item) => {
                const active = item.value === value
                const props: SectionTabLinkProps = {
                  className: tabClass,
                  'aria-current': active ? 'page' : undefined,
                  'data-active': active,
                  'data-tab': '',
                  children: content(item),
                  onKeyDown,
                }
                return (
                  <li key={item.value}>
                    {renderLink ? (
                      renderLink(item, props)
                    ) : (
                      <a
                        href={item.href}
                        className={tabClass}
                        aria-current={active ? 'page' : undefined}
                        aria-disabled={item.disabled || undefined}
                        data-active={active}
                        data-tab=""
                        onKeyDown={onKeyDown}
                      >
                        {content(item)}
                      </a>
                    )}
                  </li>
                )
              })}
            </ul>
          </nav>
        ) : (
          <div
            ref={scroller}
            role="tablist"
            aria-label={label}
            onScroll={measure}
            className={cn(scrollerClass, 'flex gap-1')}
          >
            {items.map((item) => {
              const active = item.value === value
              return (
                <button
                  key={item.value}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  aria-controls={item.controls}
                  aria-disabled={item.disabled || undefined}
                  tabIndex={active ? 0 : -1}
                  data-active={active}
                  data-tab=""
                  className={tabClass}
                  onKeyDown={onKeyDown}
                  onClick={() => !item.disabled && onValueChange?.(item.value)}
                >
                  {content(item)}
                </button>
              )
            })}
          </div>
        )}
        <span
          aria-hidden
          className={cn(
            'pointer-events-none absolute inset-y-0 left-0 w-8 bg-gradient-to-r from-background to-transparent transition-opacity motion-reduce:transition-none',
            edges.start ? 'opacity-100' : 'opacity-0',
          )}
        />
        <span
          aria-hidden
          className={cn(
            'pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-background to-transparent transition-opacity motion-reduce:transition-none',
            edges.end ? 'opacity-100' : 'opacity-0',
          )}
        />
      </div>
    </div>
  )
}
