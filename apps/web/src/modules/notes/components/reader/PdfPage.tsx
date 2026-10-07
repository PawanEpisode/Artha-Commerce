import { Button, cn, LoaderCircle, RefreshCw } from '@artha/design-system'
import { memo, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { PageTone } from '../../lib/document-types'
import { isAbort, type PdfLink, type PdfPageHandle, type PdfTextContent } from '../../lib/pdf-engine'
import { findMatches } from '../../lib/pdf-engine/search-match'
import type { PageSelection } from '../../lib/pdf-engine/text-layer'
import { rectsForRange } from '../../lib/pdf-engine/text-layer'
import { planCanvas } from '../../lib/reader-canvas'
import { PdfPageContext, type PdfPageContextValue } from './PdfPageContext'
import { TextLayer } from './TextLayer'

/** Pixels past which the first pass is a quick half-resolution draw so the page shows before the sharp one is ready. */
const DRAFT_ABOVE_PIXELS = 1_000_000

export interface PdfPageProps {
  /** 1-based page number. */
  page: number
  /** The engine's page, or null while the file is still opening (the page then shows its placeholder). */
  handle: PdfPageHandle | null
  /** Page box on screen, CSS pixels, and CSS pixels per point. */
  width: number
  height: number
  scale: number
  /** Page size in points. */
  pageW: number
  pageH: number
  /** Only live pages hold a canvas; the others are placeholders of the same size. */
  live: boolean
  tone: PageTone
  /** Device pixel ratio (the canvas uses at most 2 of it). */
  dpr?: number
  /** A small image shown under the canvas while it draws (the cover for page 1). */
  placeholderSrc?: string | null
  /** Text of an OCR page, replacing the file's own text. */
  ocrContent?: PdfTextContent | null
  /** False on a scan: the file's own text is empty, so it is not fetched. */
  useNativeText?: boolean
  /** Hits of this text are drawn on the page; `activeIndex` is the current one among them. */
  query?: string
  activeIndex?: number | null
  /** The student is offline: a page that cannot load says so instead of "could not be drawn". */
  offline?: boolean
  onSelection?: (selection: PageSelection | null) => void
  onLink?: (link: PdfLink) => void
  /** Fired once the sharp canvas of this page is on screen (and for the first-paint measurement). */
  onDrawn?: (page: number) => void
  /** Marks under the text layer (highlights, underlines, area boxes: `pointer-events-none`, `.mark-blend`). */
  marks?: ReactNode
  /** Above the text layer: ink, pins, text boxes and the capture surface of an active tool. */
  children?: ReactNode
}

type DrawState = 'idle' | 'draft' | 'drawn' | 'error'

/**
 * One page: the canvas, the invisible text layer, search hits, links, and two slots for the annotation layer.
 * Stack, bottom to top: canvas, `marks`, search hits, text layer, links, `children`. The box has its final size before
 * anything is drawn, so nothing moves when a page arrives. Off-screen pages drop their canvas (width and height 0).
 */
export const PdfPage = memo(function PdfPage({
  page,
  handle,
  width,
  height,
  scale,
  pageW,
  pageH,
  live,
  tone,
  dpr = 1,
  placeholderSrc,
  ocrContent,
  useNativeText = true,
  query,
  activeIndex,
  offline,
  onSelection,
  onLink,
  onDrawn,
  marks,
  children,
}: PdfPageProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [state, setState] = useState<DrawState>('idle')
  const [attempt, setAttempt] = useState(0)
  const [nativeText, setNativeText] = useState<PdfTextContent | null>(null)
  const [links, setLinks] = useState<PdfLink[]>([])
  const drawn = useRef<{ scale: number } | null>(null)

  const canvasScale = useMemo(() => planCanvas(pageW, pageH, scale, dpr), [pageW, pageH, scale, dpr])

  // Draw. A re-draw (zoom, resize) renders off screen and then copies over, so the old pixels stay until the new ones are ready.
  useEffect(() => {
    const canvas = canvasRef.current
    if (!live || !handle || !canvas) return
    const controller = new AbortController()
    const { signal } = controller
    void (async () => {
      try {
        const bigFirstDraw = !drawn.current && canvasScale.width * canvasScale.height > DRAFT_ABOVE_PIXELS
        if (bigFirstDraw) {
          const draft = planCanvas(pageW, pageH, scale, dpr, { draft: true })
          await handle.render(canvas, { scale: draft.renderScale, signal })
          if (signal.aborted) return
          setState('draft')
        }
        if (drawn.current || bigFirstDraw) {
          const off = document.createElement('canvas')
          try {
            await handle.render(off, { scale: canvasScale.renderScale, signal })
            if (signal.aborted) return
            canvas.width = off.width
            canvas.height = off.height
            canvas.getContext('2d')?.drawImage(off, 0, 0)
          } finally {
            off.width = 0
            off.height = 0
          }
        } else {
          await handle.render(canvas, { scale: canvasScale.renderScale, signal })
          if (signal.aborted) return
        }
        drawn.current = { scale: canvasScale.renderScale }
        setState('drawn')
        onDrawn?.(page)
      } catch (error) {
        if (isAbort(error) || signal.aborted) return
        setState('error')
      }
    })()
    return () => controller.abort()
  }, [live, handle, canvasScale, pageW, pageH, scale, dpr, page, attempt, onDrawn])

  // Off screen: free the pixels and what the engine cached for the page.
  useEffect(() => {
    if (live) return
    const canvas = canvasRef.current
    if (canvas) {
      canvas.width = 0
      canvas.height = 0
    }
    drawn.current = null
    setState('idle')
    setNativeText(null)
    handle?.release()
  }, [live, handle])
  useEffect(
    () => () => {
      const canvas = canvasRef.current
      if (canvas) {
        canvas.width = 0
        canvas.height = 0
      }
    },
    [],
  )

  // Text and links come with the first draw of a live page and are kept while it stays mounted.
  useEffect(() => {
    if (!live || !handle) return
    let cancelled = false
    if (useNativeText)
      handle
        .getText()
        .then((t) => !cancelled && setNativeText(t))
        .catch(() => undefined)
    handle
      .getLinks()
      .then((l) => !cancelled && setLinks(l))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [live, handle, useNativeText])

  const content = ocrContent ?? (useNativeText ? nativeText : null)

  const matches = useMemo(() => (content && query ? findMatches(content.text, query) : []), [content, query])
  const hitRects = useMemo(
    () => (content ? matches.map((m) => rectsForRange(content.items, m.start, m.end)) : []),
    [content, matches],
  )

  const context = useMemo<PdfPageContextValue>(
    () => ({ page, width, height, scale, pageW, pageH, tone, text: content }),
    [page, width, height, scale, pageW, pageH, tone, content],
  )
  const retry = useCallback(() => {
    setState('idle')
    setAttempt((n) => n + 1)
  }, [])

  const hasText = !!content && content.items.length > 0
  return (
    <PdfPageContext.Provider value={context}>
      <div
        role="group"
        aria-roledescription="page"
        aria-label={`Page ${page}`}
        data-page={page}
        data-page-tone={tone}
        data-state={state}
        className="page-surface group/page relative overflow-hidden shadow-soft ring-1 ring-border"
        style={{ width, height }}
      >
        {placeholderSrc && state !== 'drawn' ? (
          // The cover is a 240 px picture of this very page: a cheap first paint at the right size.
          <img
            src={placeholderSrc}
            alt=""
            aria-hidden
            draggable={false}
            className="absolute inset-0 size-full object-fill opacity-90"
          />
        ) : null}
        {/* Always mounted, so leaving the screen can set its size to 0 (Safari keeps a canvas's memory until then). */}
        <canvas
          ref={canvasRef}
          width={0}
          height={0}
          role={live && !hasText ? 'img' : undefined}
          aria-hidden={live && !hasText ? undefined : true}
          aria-label={live && !hasText ? `Page ${page}, an image without selectable text` : undefined}
          className={cn(
            'absolute inset-0 size-full',
            'in-data-[page-tone=night]:[filter:invert(1)_hue-rotate(180deg)] in-data-[page-tone=paper]:mix-blend-multiply',
          )}
        />
        {live && (state === 'idle' || state === 'draft') && !placeholderSrc ? (
          <span className="absolute inset-0 grid place-items-center text-muted-foreground" aria-hidden>
            <LoaderCircle className="size-5 animate-spin motion-reduce:animate-none" />
          </span>
        ) : null}

        {marks}

        {hitRects.length > 0 ? (
          <div aria-hidden className="pointer-events-none absolute inset-0">
            {hitRects.flatMap((rects, n) =>
              rects.map((r, i) => (
                <span
                  key={`${n}-${i}`}
                  data-hit={n === activeIndex ? 'active' : 'hit'}
                  className={cn(
                    'absolute rounded-sm mix-blend-multiply',
                    n === activeIndex ? 'bg-primary/50 ring-2 ring-primary' : 'bg-primary/25',
                  )}
                  style={{
                    left: `${r[0] * 100}%`,
                    top: `${r[1] * 100}%`,
                    width: `${r[2] * 100}%`,
                    height: `${r[3] * 100}%`,
                  }}
                />
              )),
            )}
          </div>
        ) : null}

        {content ? (
          <TextLayer
            content={content}
            page={page}
            pageW={pageW}
            pageH={pageH}
            height={height}
            kind={ocrContent ? 'ocr' : 'native'}
            onSelection={onSelection}
          />
        ) : null}

        {links.map((link, i) => {
          const style = {
            left: `${link.rect[0] * 100}%`,
            top: `${link.rect[1] * 100}%`,
            width: `${link.rect[2] * 100}%`,
            height: `${link.rect[3] * 100}%`,
          }
          const label = link.kind === 'external' ? `Link to ${safeHost(link.url)}` : `Go to page ${link.page}`
          return (
            <a
              key={i}
              href={link.kind === 'external' ? link.url : `#page-${link.page}`}
              rel="noopener noreferrer"
              target={link.kind === 'external' ? '_blank' : undefined}
              aria-label={label}
              style={style}
              className="absolute rounded-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/60"
              onClick={(e) => {
                e.preventDefault()
                onLink?.(link)
              }}
            />
          )
        })}

        {children}

        {state === 'error' ? (
          <div
            role="alert"
            className="absolute inset-0 z-20 grid place-items-center bg-card/90 p-4 text-center text-sm text-foreground"
          >
            <div className="flex max-w-xs flex-col items-center gap-3">
              <p>{offline ? 'This page is not available offline.' : 'This page could not be drawn.'}</p>
              <Button variant="outline" onClick={retry}>
                <RefreshCw aria-hidden />
                Retry
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </PdfPageContext.Provider>
  )
})

function safeHost(url: string): string {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'mailto:' ? parsed.pathname : parsed.host
  } catch {
    return 'an external site'
  }
}
