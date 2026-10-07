import { Popover as PopoverPrimitive, Toolbar as ToolbarPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'
import { Button } from './button'

/** Where the toolbar points: a rectangle in viewport coordinates, an element, or a function that reads either fresh. */
export type FloatingToolbarAnchor = DOMRect | Element | (() => DOMRect | Element | null) | null

function readRect(anchor: FloatingToolbarAnchor): DOMRect {
  const target = typeof anchor === 'function' ? anchor() : anchor
  if (!target) return new DOMRect(0, 0, 0, 0)
  return target instanceof Element ? target.getBoundingClientRect() : target
}

const BASE_PADDING = 8
const TABBABLE = 'button, [role="radio"], [href], input, select, textarea, [tabindex]'

/** Controls inside `root` that are in the tab order right now (roving groups expose one). */
function tabbablesIn(root: HTMLElement | null): HTMLElement[] {
  if (!root) return []
  return Array.from(root.querySelectorAll<HTMLElement>(TABBABLE)).filter(
    (el) => el.tabIndex >= 0 && !el.hasAttribute('disabled'),
  )
}

/** Safe-area insets in px (notches, home indicator), read once per open through a probe element. Zero where unsupported. */
function readSafeArea() {
  const probe = document.createElement('div')
  probe.setAttribute('aria-hidden', 'true')
  probe.style.cssText =
    'position:fixed;visibility:hidden;pointer-events:none;padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)'
  document.body.appendChild(probe)
  const style = getComputedStyle(probe)
  const px = (v: string) => Number.parseFloat(v) || 0
  const insets = {
    top: px(style.paddingTop),
    right: px(style.paddingRight),
    bottom: px(style.paddingBottom),
    left: px(style.paddingLeft),
  }
  probe.remove()
  return insets
}

export interface FloatingToolbarProps {
  /** Hidden and removed from the reading order until true. */
  open: boolean
  /** Called with false on Escape or when the pointer or focus goes elsewhere. The app owns `open`. */
  onOpenChange: (open: boolean) => void
  /** What the toolbar points at, in viewport coordinates. A function is read again on every scroll and resize. */
  anchor: FloatingToolbarAnchor
  /** Accessible name of the toolbar ("Highlight tools"). */
  label: string
  /** The scroll container the anchor lives in, so the toolbar follows when that container (not the page) scrolls. */
  scrollContainer?: Element | null
  /** Preferred side. It flips to the other side when there is no room. Default `top`. */
  side?: 'top' | 'bottom'
  /** Receives focus when the toolbar closes, unless the person clicked or tapped elsewhere. */
  returnFocusRef?: React.RefObject<HTMLElement | null>
  /** Move focus into the toolbar on open. Default false: a selection toolbar must not steal focus from the page. */
  autoFocus?: boolean
  /** Keyboard shortcut that moves focus into the open toolbar (the toolbar is in a portal, so Tab does not reach it). */
  focusKey?: string
  className?: string
  children: React.ReactNode
}

/**
 * A toolbar that floats next to a rectangle (a text selection, a pin), for example the colour and action bar after the
 * student selects text. Placement is collision aware (flips above or below, slides to stay inside the viewport and the
 * safe areas) and follows scroll and resize. It is `role="toolbar"` with roving tabindex and arrow keys (Left, Right,
 * Home, End), it does not trap focus and nothing in it is hover only. Escape closes it and returns focus to
 * `returnFocusRef`. Compose it from `FloatingToolbarButton`, `FloatingToolbarSeparator` and other controls such as
 * `SwatchPicker`.
 */
export function FloatingToolbar({
  open,
  onOpenChange,
  anchor,
  label,
  scrollContainer,
  side = 'top',
  returnFocusRef,
  autoFocus = false,
  focusKey = 'F10',
  className,
  children,
}: FloatingToolbarProps) {
  const rootRef = React.useRef<HTMLDivElement>(null)
  const clickedAwayRef = React.useRef(false)
  const [safeArea, setSafeArea] = React.useState({ top: 0, right: 0, bottom: 0, left: 0 })

  // A fresh virtual element when the anchor changes makes Popper measure again; the function inside reads live.
  const virtualRef = React.useMemo(
    () => ({
      current: {
        getBoundingClientRect: () => readRect(anchor),
        contextElement: scrollContainer ?? undefined,
      },
    }),
    [anchor, scrollContainer],
  )

  React.useEffect(() => {
    if (!open) return
    clickedAwayRef.current = false
    setSafeArea(readSafeArea())
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== focusKey || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
      const first = rootRef.current?.querySelector<HTMLElement>(
        'button:not([disabled]), [role="radio"]:not([disabled])',
      )
      if (!first) return
      event.preventDefault()
      first.focus()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, focusKey])

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <PopoverPrimitive.Anchor virtualRef={virtualRef} />
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          asChild
          side={side}
          align="center"
          sideOffset={10}
          avoidCollisions
          sticky="always"
          collisionPadding={{
            top: BASE_PADDING + safeArea.top,
            right: BASE_PADDING + safeArea.right,
            bottom: BASE_PADDING + safeArea.bottom,
            left: BASE_PADDING + safeArea.left,
          }}
          onOpenAutoFocus={(event) => {
            if (!autoFocus) event.preventDefault()
          }}
          onPointerDownOutside={() => {
            clickedAwayRef.current = true
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            if (!clickedAwayRef.current) returnFocusRef?.current?.focus()
          }}
        >
          <ToolbarPrimitive.Root
            ref={rootRef}
            role="toolbar"
            aria-label={label}
            aria-orientation="horizontal"
            data-slot="floating-toolbar"
            onKeyDown={(event) => {
              // Radix Popover loops Tab inside its content. A selection toolbar must never trap focus, so Tab off
              // either end leaves it (and closes it); focus goes back to `returnFocusRef` through onCloseAutoFocus.
              if (event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey) return
              const stops = tabbablesIn(rootRef.current)
              const edge = event.shiftKey ? stops[0] : stops[stops.length - 1]
              if (stops.length === 0 || document.activeElement === edge) {
                event.preventDefault()
                onOpenChange(false)
              }
            }}
            className={cn(
              'z-50 flex max-w-[calc(100vw-1rem)] flex-wrap items-center gap-1 rounded-xl border border-border bg-popover p-1 text-popover-foreground shadow-(--shadow-lift) data-[state=open]:animate-in data-[state=open]:fade-in-0 motion-reduce:animate-none',
              className,
            )}
          >
            {children}
          </ToolbarPrimitive.Root>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}

/** A button in a FloatingToolbar. Part of the roving tabindex. Icon-only buttons need an `aria-label`. */
export function FloatingToolbarButton({
  className,
  variant = 'ghost',
  size = 'icon',
  ...props
}: React.ComponentProps<typeof Button>) {
  return (
    <ToolbarPrimitive.Button asChild>
      <Button data-slot="floating-toolbar-button" variant={variant} size={size} className={className} {...props} />
    </ToolbarPrimitive.Button>
  )
}

export function FloatingToolbarSeparator({
  className,
  ...props
}: React.ComponentProps<typeof ToolbarPrimitive.Separator>) {
  return (
    <ToolbarPrimitive.Separator
      data-slot="floating-toolbar-separator"
      className={cn('mx-0.5 h-6 w-px shrink-0 bg-border', className)}
      {...props}
    />
  )
}
