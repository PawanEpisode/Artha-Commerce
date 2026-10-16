import { Slot } from 'radix-ui'
import * as React from 'react'

import { type LucideIcon, Menu, PanelLeft, PanelLeftClose } from '../../icons'
import { cn } from '../../lib/utils'
import { Button } from './button'
import { Sheet, SheetContent, SheetTitle } from './sheet'

/**
 * App sidebar: a pinned rail that is either expanded (232 px) or collapsed to an icon rail (48 px).
 *
 * - The pinned state is stored in localStorage and mirrored on `<html data-sidebar="collapsed">` by SIDEBAR_INIT_SCRIPT
 *   before first paint, so a collapsed rail never flashes open. All widths come from CSS variables (see styles.css).
 * - Collapsed + pointer over the rail (or keyboard focus in it): the rail opens as an OVERLAY. The page does not move,
 *   because the spacer keeps the collapsed width. It closes when the pointer leaves, on Escape, or after a link is used.
 * - Under `md` there is no rail: the same content opens as a left drawer from a menu button in the topbar.
 * - `[` toggles the pinned state.
 */

const STORAGE_KEY = 'artha:sidebar'

/** Inline in <head>: applies the stored collapsed state before paint. */
export const SIDEBAR_INIT_SCRIPT = `try{if(localStorage.getItem('${STORAGE_KEY}')==='collapsed')document.documentElement.dataset.sidebar='collapsed'}catch(e){}`

interface SidebarContextValue {
  collapsed: boolean
  peek: boolean
  mobileOpen: boolean
  toggle: () => void
  setCollapsed: (collapsed: boolean) => void
  setPeek: (peek: boolean) => void
  /** Keep the rail open while a menu opened from it is showing. */
  holdPeek: (hold: boolean) => void
  setMobileOpen: (open: boolean) => void
}

const SidebarContext = React.createContext<SidebarContextValue | null>(null)

export function useSidebar(): SidebarContextValue {
  const ctx = React.useContext(SidebarContext)
  if (!ctx) throw new Error('useSidebar must be used inside <SidebarProvider>')
  return ctx
}

const isEditable = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsedState] = React.useState(false)
  const [peek, setPeekState] = React.useState(false)
  const [mobileOpen, setMobileOpen] = React.useState(false)
  const held = React.useRef(false)

  // Read the stored choice once on the client. The html attribute already drew the right width.
  React.useEffect(() => {
    setCollapsedState(document.documentElement.dataset.sidebar === 'collapsed')
  }, [])

  const setCollapsed = React.useCallback((next: boolean) => {
    setCollapsedState(next)
    setPeekState(false)
    if (next) document.documentElement.dataset.sidebar = 'collapsed'
    else delete document.documentElement.dataset.sidebar
    try {
      localStorage.setItem(STORAGE_KEY, next ? 'collapsed' : 'open')
    } catch {
      /* storage can be blocked; the choice then lasts for this visit only */
    }
  }, [])

  const toggle = React.useCallback(() => setCollapsed(!collapsed), [collapsed, setCollapsed])
  const setPeek = React.useCallback((next: boolean) => {
    if (!next && held.current) return
    setPeekState(next)
  }, [])
  const holdPeek = React.useCallback((hold: boolean) => {
    held.current = hold
    if (!hold) setPeekState(false)
  }, [])

  React.useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPeekState(false)
      if (event.key === '[' && !event.metaKey && !event.ctrlKey && !event.altKey && !isEditable(event.target)) {
        event.preventDefault()
        toggle()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggle])

  const value = React.useMemo(
    () => ({ collapsed, peek, mobileOpen, toggle, setCollapsed, setPeek, holdPeek, setMobileOpen }),
    [collapsed, peek, mobileOpen, toggle, setCollapsed, setPeek, holdPeek],
  )
  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>
}

interface SidebarProps {
  /** Accessible name of the navigation landmark. */
  label: string
  children: React.ReactNode
}

export function Sidebar({ label, children }: SidebarProps) {
  const { collapsed, peek, setPeek, mobileOpen, setMobileOpen } = useSidebar()
  const timer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const ref = React.useRef<HTMLDivElement>(null)
  const open = peek && collapsed

  const later = (next: boolean, ms: number) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setPeek(next), ms)
  }
  React.useEffect(() => () => clearTimeout(timer.current), [])

  return (
    <>
      {/* Keeps the collapsed width in the layout so the open overlay never pushes the page. */}
      <div
        aria-hidden
        className="hidden w-[var(--sidebar-w)] shrink-0 transition-[width] duration-200 ease-out motion-reduce:transition-none md:block"
      />
      {/* The wrapper is the fixed column (z-40: above sticky bars like SectionTabs at z-30, below dialogs at z-50). It does not clip,
          so the edge toggle can sit half outside the rail. The aside inside clips the labels of a collapsed rail. */}
      <div
        data-slot="sidebar-rail"
        style={{ width: open ? 'var(--sidebar-w-open)' : 'var(--sidebar-w)' }}
        className="group/rail fixed inset-y-0 left-0 z-40 hidden transition-[width] duration-200 ease-out motion-reduce:transition-none md:block"
        onPointerEnter={(e) => {
          if (e.pointerType === 'mouse' && collapsed) later(true, 90)
        }}
        onPointerLeave={(e) => {
          if (e.pointerType === 'mouse') later(false, 140)
        }}
        onFocusCapture={(e) => {
          if (collapsed && (e.target as HTMLElement).matches(':focus-visible')) setPeek(true)
        }}
        onBlurCapture={(e) => {
          if (!ref.current?.contains(e.relatedTarget as Node | null)) setPeek(false)
        }}
        onClickCapture={(e) => {
          // Using a link closes the overlay at once, so it does not sit over the page that just opened.
          if ((e.target as HTMLElement).closest('a[href]')) {
            clearTimeout(timer.current)
            setPeek(false)
          }
        }}
        ref={ref}
      >
        <aside
          aria-label={label}
          data-slot="sidebar"
          data-peek={open ? 'true' : 'false'}
          className={cn(
            'h-full w-full overflow-hidden border-r bg-sidebar transition-shadow duration-200 motion-reduce:transition-none',
            open && 'shadow-lift',
          )}
        >
          <div className="flex h-full w-[var(--sidebar-w-open)] flex-col">{children}</div>
        </aside>
        <SidebarTrigger className="absolute top-[13px] -right-3 z-10 size-6 rounded-full border bg-background text-muted-foreground opacity-0 shadow-soft transition-opacity group-hover/rail:opacity-100 hover:text-foreground focus-visible:opacity-100 motion-reduce:transition-none [&_svg]:size-3.5" />
      </div>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="bg-sidebar" aria-describedby={undefined}>
          <SheetTitle className="sr-only">{label}</SheetTitle>
          <nav aria-label={label} className="flex h-full flex-col" data-sidebar-mobile>
            {children}
          </nav>
        </SheetContent>
      </Sheet>
    </>
  )
}

export function SidebarHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sidebar-header"
      className={cn('flex h-11 shrink-0 items-center gap-1 px-2', className)}
      {...props}
    />
  )
}

export function SidebarContent({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sidebar-content"
      className={cn('flex min-h-0 flex-1 flex-col gap-1 overflow-x-hidden overflow-y-auto px-1.5 py-1', className)}
      {...props}
    />
  )
}

export function SidebarFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sidebar-footer"
      className={cn('flex shrink-0 flex-col gap-0.5 border-t p-1.5', className)}
      {...props}
    />
  )
}

export function SidebarGroup({
  label,
  className,
  children,
  ...props
}: Omit<React.ComponentProps<'div'>, 'children'> & { label?: string; children: React.ReactNode }) {
  const id = React.useId()
  return (
    <div
      data-slot="sidebar-group"
      role="group"
      aria-labelledby={label ? id : undefined}
      className={cn('pb-1', className)}
      {...props}
    >
      {label ? (
        <div
          id={id}
          data-slot="sidebar-group-label"
          className="flex h-6 items-center px-2.5 text-[11px] font-medium tracking-wide whitespace-nowrap text-muted-foreground uppercase transition-opacity rail:opacity-0"
        >
          {label}
        </div>
      ) : null}
      <ul className="flex flex-col gap-px">{children}</ul>
    </div>
  )
}

export const sidebarItemClass =
  'group/item relative flex h-7 w-full cursor-pointer items-center gap-2.5 rounded-md px-2.5 text-left text-[13px] font-medium whitespace-nowrap text-muted-foreground outline-none transition-colors hover:bg-sidebar-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 aria-[current=page]:bg-sidebar-accent aria-[current=page]:text-foreground data-[active=true]:bg-sidebar-accent data-[active=true]:text-foreground motion-reduce:transition-none pointer-coarse:h-10 rail:text-[0px] [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 aria-[current=page]:[&_svg]:text-primary'

interface SidebarItemProps extends React.ComponentProps<'button'> {
  icon?: LucideIcon
  /** Render the single child (a router Link) instead of a button. */
  asChild?: boolean
  /** Trailing content (a count, a shortcut). Hidden while the rail is collapsed. */
  trailing?: React.ReactNode
}

export function SidebarItem({
  icon: Icon,
  asChild = false,
  trailing,
  className,
  children,
  onClick,
  ...props
}: SidebarItemProps) {
  const { setMobileOpen } = useSidebar()
  const Comp = asChild ? Slot.Root : 'button'
  return (
    <li className="list-none">
      <Comp
        data-slot="sidebar-item"
        className={cn(sidebarItemClass, className)}
        {...(asChild ? {} : { type: 'button' as const })}
        onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
          onClick?.(e)
          setMobileOpen(false)
        }}
        {...props}
      >
        {Icon ? <Icon aria-hidden /> : null}
        <Slot.Slottable>{children}</Slot.Slottable>
        {trailing ? (
          <span className="ml-auto flex items-center gap-1 text-[11px] text-muted-foreground rail:hidden">
            {trailing}
          </span>
        ) : null}
      </Comp>
    </li>
  )
}

/** Collapse / expand the pinned rail (desktop). */
export function SidebarTrigger({ className }: { className?: string }) {
  const { collapsed, toggle } = useSidebar()
  const Icon = collapsed ? PanelLeft : PanelLeftClose
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      className={cn('text-muted-foreground', className)}
      aria-label={collapsed ? 'Pin sidebar open' : 'Collapse sidebar'}
      aria-keyshortcuts="["
      onClick={toggle}
    >
      <Icon />
    </Button>
  )
}

/** Opens the drawer under `md`. */
export function SidebarMobileTrigger({ className }: { className?: string }) {
  const { setMobileOpen } = useSidebar()
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      className={cn('md:hidden', className)}
      aria-label="Open navigation"
      onClick={() => setMobileOpen(true)}
    >
      <Menu />
    </Button>
  )
}

/** The column to the right of the rail: topbar and page. */
export function SidebarInset({ className, ...props }: React.ComponentProps<'div'>) {
  return <div data-slot="sidebar-inset" className={cn('flex min-w-0 flex-1 flex-col', className)} {...props} />
}
