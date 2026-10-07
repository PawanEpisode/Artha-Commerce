import { cn } from '@artha/design-system'
import {
  type ReactNode,
  type Ref,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import type { PageTone } from '../../lib/document-types'
import type { PdfDocumentHandle, PdfLink, PdfTextContent } from '../../lib/pdf-engine'
import type { PageSelection } from '../../lib/pdf-engine/text-layer'
import {
  type Anchor,
  anchorAt,
  clampPage,
  computeLayout,
  currentPageAt,
  fitWidthFor,
  type PageBox,
  pageWindow,
  scrollTopForPage,
  yForAnchor,
} from '../../lib/reader-layout'
import type { ZoomSpec } from '../../lib/reader-schema'
import { doubleTapZoom, percentFor, pinchPercent, stepZoom } from '../../lib/reader-zoom'
import { PdfPage } from './PdfPage'

/** One mouse-wheel notch reports a delta of 100; a trackpad pinch reports 1 to 10. Both should feel like a small step. */
const WHEEL_ZOOM_MAX_DELTA = 20

export interface ViewportHandle {
  scrollToPage: (page: number) => void
  zoomIn: () => void
  zoomOut: () => void
  zoomFit: () => void
  /** The element that scrolls, for focus return and tests. */
  element: () => HTMLElement | null
}

/** What a page may carry beyond the canvas: OCR text, search hits and the annotation layer's two slots. */
export interface PageExtras {
  ocrContent?: PdfTextContent | null
  useNativeText?: boolean
  query?: string
  activeIndex?: number | null
  marks?: ReactNode
  children?: ReactNode
}

export interface PdfViewportProps {
  /** The open file, or null while it opens: pages are placeholders of their final size until then. */
  doc: PdfDocumentHandle | null
  /** Size of every page in points (stored `page_meta`, or what the engine reported). */
  sizes: ReadonlyArray<PageBox>
  zoom: ZoomSpec
  tone: PageTone
  /** 1-based page to open at. Read once, at mount (and again if `restoreKey` changes). */
  initialPage: number
  /** A request to scroll to a page: a new `nonce` scrolls again even to the same page. */
  jumpTo?: { page: number; nonce: number } | null
  onPageChange: (page: number) => void
  onZoomChange: (zoom: ZoomSpec) => void
  /** Fired when the student scrolls clearly down or up (the bars follow it). */
  onScrollDirection?: (direction: 'up' | 'down') => void
  /** A tap in the middle third of the reading area (shows or hides the bars). */
  onTapMiddle?: () => void
  /** Pages whose placeholders are mounted, so sizes can be fetched lazily when `page_meta` is missing. */
  onWindowChange?: (range: [number, number] | null) => void
  onPageDrawn?: (page: number) => void
  onSelection?: (selection: PageSelection | null) => void
  onLink?: (link: PdfLink) => void
  pageExtras?: (page: number) => PageExtras
  coverUrl?: string | null
  large?: boolean
  offline?: boolean
  /** Space for the bars above the first page and below the last, CSS pixels. */
  padTop?: number
  padBottom?: number
  ref?: Ref<ViewportHandle>
  className?: string
}

const TAP_MS = 300
const TAP_SLOP = 12
const DOUBLE_TAP_SLOP = 40
const DIRECTION_SLOP = 10

interface Pointer {
  x: number
  y: number
}

/**
 * The reading area: continuous vertical scroll of every page at its final size, only the pages near the viewport in the
 * DOM and only about five of them with a canvas. Fit width by default; pinch, double tap, Ctrl + wheel, keys and the
 * toolbar change the zoom, and a zoomed page pans inside the area. The spot under the fingers stays put when the zoom or
 * the page sizes change.
 */
export function PdfViewport({
  doc,
  sizes,
  zoom,
  tone,
  initialPage,
  jumpTo,
  onPageChange,
  onZoomChange,
  onScrollDirection,
  onTapMiddle,
  onWindowChange,
  onPageDrawn,
  onSelection,
  onLink,
  pageExtras,
  coverUrl,
  large = false,
  offline,
  padTop = 8,
  padBottom = 8,
  ref,
  className,
}: PdfViewportProps) {
  const scroller = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const [area, setArea] = useState({ width: 0, height: 0 })
  const [scrollTop, setScrollTop] = useState(0)
  const [dpr, setDpr] = useState(1)

  const layout = useMemo(
    () => computeLayout(sizes, zoom, { availWidth: area.width, padTop, padBottom }),
    [sizes, zoom, area.width, padTop, padBottom],
  )
  const layoutRef = useRef(layout)
  layoutRef.current = layout
  const zoomRef = useRef(zoom)
  zoomRef.current = zoom

  // Measure the reading area.
  useLayoutEffect(() => {
    const el = scroller.current
    if (!el) return
    const measure = () => setArea({ width: el.clientWidth, height: el.clientHeight })
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    setDpr(window.devicePixelRatio || 1)
    return () => observer.disconnect()
  }, [])

  // Keep the same spot when the layout changes (zoom, resize, a page size learned late).
  const spot = useRef<{ anchor: Anchor; focalY: number; fx: number; focalX: number; contentWidth: number } | null>(null)
  const capture = useCallback((focalX?: number, focalY?: number) => {
    const el = scroller.current
    if (!el) return
    const fy = focalY ?? Math.min(el.clientHeight / 3, 200)
    const fx = focalX ?? el.clientWidth / 2
    const l = layoutRef.current
    spot.current = {
      anchor: anchorAt(l, el.scrollTop + fy),
      focalY: fy,
      focalX: fx,
      fx: (el.scrollLeft + fx) / Math.max(1, l.contentWidth),
      contentWidth: l.contentWidth,
    }
  }, [])
  const restored = useRef(false)
  useLayoutEffect(() => {
    const el = scroller.current
    if (!el || area.width === 0 || layout.tops.length === 0) return
    if (!restored.current) {
      restored.current = true
      el.scrollTop = scrollTopForPage(layout, clampPage(initialPage, layout.tops.length) - 1)
      setScrollTop(el.scrollTop)
      return
    }
    const s = spot.current
    if (!s) return
    el.scrollTop = Math.max(0, yForAnchor(layout, s.anchor) - s.focalY)
    el.scrollLeft = Math.max(0, s.fx * layout.contentWidth - s.focalX)
    setScrollTop(el.scrollTop)
    // Only the layout drives this; `initialPage` is read once above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout])

  // Scroll: remember the spot, tell the parent the page and the direction, move the window.
  const lastTop = useRef(0)
  const lastPage = useRef(0)
  const frame = useRef(0)
  const onScroll = useCallback(() => {
    if (frame.current) return
    frame.current = requestAnimationFrame(() => {
      frame.current = 0
      const el = scroller.current
      if (!el) return
      const top = el.scrollTop
      capture()
      setScrollTop(top)
      const delta = top - lastTop.current
      if (Math.abs(delta) > DIRECTION_SLOP) {
        onScrollDirection?.(delta > 0 ? 'down' : 'up')
        lastTop.current = top
      }
      const l = layoutRef.current
      const page = currentPageAt(l, top, el.clientHeight) + 1
      if (page !== lastPage.current && l.tops.length > 0) {
        lastPage.current = page
        onPageChange(page)
      }
    })
  }, [capture, onPageChange, onScrollDirection])
  useEffect(() => () => cancelAnimationFrame(frame.current), [])

  // Programmatic jumps (outline, scrubber, search hit, keys).
  const scrollToPage = useCallback(
    (page: number) => {
      const el = scroller.current
      if (!el) return
      const l = layoutRef.current
      el.scrollTop = scrollTopForPage(l, clampPage(page, l.tops.length) - 1)
      lastPage.current = 0
      setScrollTop(el.scrollTop)
      onScrollDirection?.('up')
      onPageChange(clampPage(page, l.tops.length))
      lastPage.current = clampPage(page, l.tops.length)
    },
    [onPageChange, onScrollDirection],
  )
  const jumpNonce = useRef<number | null>(null)
  useEffect(() => {
    if (!jumpTo || jumpTo.nonce === jumpNonce.current || area.width === 0) return
    jumpNonce.current = jumpTo.nonce
    scrollToPage(jumpTo.page)
  }, [jumpTo, area.width, scrollToPage])

  // Zoom helpers. The percent on screen comes from the page in view.
  const currentPercent = useCallback(() => {
    const l = layoutRef.current
    const el = scroller.current
    const index = el ? currentPageAt(l, el.scrollTop, el.clientHeight) : 0
    const box = sizes[index] ?? sizes[0]
    return box ? percentFor(zoomRef.current, fitWidthFor(el?.clientWidth ?? 360), box.w) : 100
  }, [sizes])
  const applyZoom = useCallback(
    (next: ZoomSpec, focalX?: number, focalY?: number) => {
      capture(focalX, focalY)
      onZoomChange(next)
    },
    [capture, onZoomChange],
  )
  const zoomIn = useCallback(() => applyZoom(stepZoom(currentPercent(), 1)), [applyZoom, currentPercent])
  const zoomOut = useCallback(() => applyZoom(stepZoom(currentPercent(), -1)), [applyZoom, currentPercent])
  const zoomFit = useCallback(() => applyZoom('fit'), [applyZoom])
  useImperativeHandle(ref, () => ({ scrollToPage, zoomIn, zoomOut, zoomFit, element: () => scroller.current }), [
    scrollToPage,
    zoomIn,
    zoomOut,
    zoomFit,
  ])

  // Pinch, double tap and tap (pointer events). The pinch scales the whole content with a CSS transform for a smooth
  // preview and commits the new zoom when the fingers lift.
  const pointers = useRef(new Map<number, Pointer>())
  const pinch = useRef<{ dist: number; percent: number; cx: number; cy: number; ratio: number } | null>(null)
  const tap = useRef<{ x: number; y: number; t: number; moved: boolean; id: number } | null>(null)
  const lastTap = useRef<{ x: number; y: number; t: number } | null>(null)
  const tapTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const distance = () => {
    const [a, b] = [...pointers.current.values()]
    return a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0
  }
  const onPointerDown = (e: React.PointerEvent) => {
    if (e.pointerType === 'mouse') return
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.current.size === 2) {
      const el = scroller.current
      const rect = el?.getBoundingClientRect()
      const [a, b] = [...pointers.current.values()] as [Pointer, Pointer]
      const cx = (a.x + b.x) / 2 - (rect?.left ?? 0)
      const cy = (a.y + b.y) / 2 - (rect?.top ?? 0)
      pinch.current = { dist: distance(), percent: currentPercent(), cx, cy, ratio: 1 }
      tap.current = null
      capture(cx, cy)
      if (content.current && el)
        content.current.style.transformOrigin = `${el.scrollLeft + cx}px ${el.scrollTop + cy}px`
    } else if (pointers.current.size === 1) {
      tap.current = { x: e.clientX, y: e.clientY, t: e.timeStamp, moved: false, id: e.pointerId }
    }
  }
  const onPointerMove = (e: React.PointerEvent) => {
    const p = pointers.current.get(e.pointerId)
    if (!p) return
    p.x = e.clientX
    p.y = e.clientY
    if (tap.current && Math.hypot(e.clientX - tap.current.x, e.clientY - tap.current.y) > TAP_SLOP)
      tap.current.moved = true
    if (pinch.current && pointers.current.size >= 2) {
      const ratio = distance() / Math.max(1, pinch.current.dist)
      const clamped = pinchPercent(pinch.current.percent, ratio) / pinch.current.percent
      pinch.current.ratio = clamped
      if (content.current) content.current.style.transform = `scale(${clamped})`
    }
  }
  const endPointer = (e: React.PointerEvent, cancelled = false) => {
    if (!pointers.current.has(e.pointerId)) return
    pointers.current.delete(e.pointerId)
    if (pinch.current) {
      if (pointers.current.size < 2) {
        const g = pinch.current
        pinch.current = null
        if (content.current) {
          content.current.style.transform = ''
          content.current.style.transformOrigin = ''
        }
        if (Math.abs(g.ratio - 1) > 0.02) onZoomChange(pinchPercent(g.percent, g.ratio))
      }
      tap.current = null
      return
    }
    const t = tap.current
    tap.current = null
    if (cancelled || !t || t.moved || t.id !== e.pointerId || e.timeStamp - t.t > TAP_MS) return
    if (window.getSelection()?.toString()) return
    const el = scroller.current
    const rect = el?.getBoundingClientRect()
    const prev = lastTap.current
    if (
      prev &&
      e.timeStamp - prev.t < TAP_MS + 100 &&
      Math.hypot(prev.x - e.clientX, prev.y - e.clientY) < DOUBLE_TAP_SLOP
    ) {
      lastTap.current = null
      if (tapTimer.current) clearTimeout(tapTimer.current)
      const l = layoutRef.current
      const index = el ? currentPageAt(l, el.scrollTop, el.clientHeight) : 0
      const box = sizes[index] ?? sizes[0]
      const fit = box ? percentFor('fit', fitWidthFor(el?.clientWidth ?? 360), box.w) : 100
      applyZoom(doubleTapZoom(zoomRef.current, fit), e.clientX - (rect?.left ?? 0), e.clientY - (rect?.top ?? 0))
      return
    }
    lastTap.current = { x: e.clientX, y: e.clientY, t: e.timeStamp }
    const y = e.clientY - (rect?.top ?? 0)
    const h = rect?.height ?? 1
    if (tapTimer.current) clearTimeout(tapTimer.current)
    tapTimer.current = setTimeout(() => {
      lastTap.current = null
      if (y > h / 3 && y < (2 * h) / 3) onTapMiddle?.()
    }, TAP_MS + 100)
  }
  useEffect(() => () => void (tapTimer.current && clearTimeout(tapTimer.current)), [])

  // Ctrl + wheel (a trackpad pinch, or Ctrl and the wheel) zooms the reader; the browser's own zoom keys stay untouched.
  useEffect(() => {
    const el = scroller.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      applyZoom(
        pinchPercent(
          currentPercent(),
          Math.exp(-Math.max(-WHEEL_ZOOM_MAX_DELTA, Math.min(WHEEL_ZOOM_MAX_DELTA, e.deltaY)) * 0.01),
        ),
        e.clientX - rect.left,
        e.clientY - rect.top,
      )
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [applyZoom, currentPercent])

  // Which pages are in the DOM and which hold a canvas.
  const win = useMemo(
    () => pageWindow(layout, scrollTop, area.height, { ahead: large ? 2 : 1 }),
    [layout, scrollTop, area.height, large],
  )
  const mountedKey = win.mounted ? `${win.mounted[0]}-${win.mounted[1]}` : ''
  useEffect(() => {
    onWindowChange?.(win.mounted)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mountedKey])
  const live = useMemo(() => new Set(win.live), [win.live])

  const pages: ReactNode[] = []
  if (win.mounted && area.width > 0) {
    for (let i = win.mounted[0]; i <= win.mounted[1]; i++) {
      const size = sizes[i]
      if (!size) continue
      const extras = pageExtras?.(i + 1) ?? {}
      pages.push(
        <div
          key={i}
          className="absolute"
          style={{ top: layout.tops[i], left: Math.max(0, (layout.contentWidth - (layout.widths[i] as number)) / 2) }}
        >
          <PdfPage
            page={i + 1}
            handle={doc ? doc.getPage(i + 1) : null}
            width={layout.widths[i] as number}
            height={layout.heights[i] as number}
            scale={layout.scales[i] as number}
            pageW={size.w}
            pageH={size.h}
            live={live.has(i)}
            tone={tone}
            dpr={dpr}
            placeholderSrc={i === 0 ? coverUrl : null}
            offline={offline}
            onDrawn={onPageDrawn}
            onSelection={onSelection}
            onLink={onLink}
            {...extras}
          />
        </div>,
      )
    }
  }

  return (
    <div
      ref={scroller}
      role="region"
      aria-label="Document pages"
      /* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrolling area must be reachable by keyboard (WCAG 2.1.1) */
      tabIndex={0}
      data-slot="pdf-viewport"
      data-page-tone={tone}
      onScroll={onScroll}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={(e) => endPointer(e)}
      onPointerCancel={(e) => endPointer(e, true)}
      className={cn(
        'relative h-full w-full touch-pan-x touch-pan-y overflow-auto overscroll-contain bg-muted outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 focus-visible:ring-inset',
        className,
      )}
    >
      <div
        ref={content}
        className="relative will-change-transform"
        style={{ width: layout.contentWidth, height: layout.total }}
      >
        {pages}
      </div>
    </div>
  )
}
