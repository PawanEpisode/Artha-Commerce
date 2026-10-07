import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createRef } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { PdfDocumentHandle } from '../../lib/pdf-engine'
import { createFakeEngine } from '../../lib/pdf-engine/fake-engine'
import { computeLayout } from '../../lib/reader-layout'
import { PdfViewport, type PdfViewportProps, type ViewportHandle } from './PdfViewport'

const SIZE = { w: 595, h: 842 }
const sizes = (n: number) => Array.from({ length: n }, () => SIZE)

async function open(pages = 100): Promise<PdfDocumentHandle> {
  const engine = createFakeEngine({ pageCount: pages })
  return engine.open({ url: { get: () => 'u', refresh: async () => 'u' }, requestPassword: async () => null })
}

beforeEach(() => {
  vi.spyOn(Element.prototype, 'clientWidth', 'get').mockReturnValue(376)
  vi.spyOn(Element.prototype, 'clientHeight', 'get').mockReturnValue(700)
})
afterEach(() => vi.restoreAllMocks())

const props = (over: Partial<PdfViewportProps> = {}): PdfViewportProps => ({
  doc: null,
  sizes: sizes(100),
  zoom: 'fit',
  tone: 'original',
  initialPage: 1,
  onPageChange: () => undefined,
  onZoomChange: () => undefined,
  padTop: 64,
  padBottom: 112,
  ...over,
})

const region = () => screen.getByRole('region', { name: 'Document pages' })
const scrollTo = async (top: number) => {
  const el = region()
  await act(async () => {
    el.scrollTop = top
    fireEvent.scroll(el)
    await new Promise((r) => requestAnimationFrame(() => r(null)))
  })
}
const liveCanvases = (c: HTMLElement) => Array.from(c.querySelectorAll('canvas')).filter((x) => x.width > 0).length

describe('PdfViewport', () => {
  it('lays out every page at its final size before anything is drawn, so nothing shifts', () => {
    render(<PdfViewport {...props()} />)
    const layout = computeLayout(sizes(100), 'fit', { availWidth: 376, padTop: 64, padBottom: 112 })
    const first = screen.getByRole('group', { name: 'Page 1' })
    expect(first).toHaveStyle({ width: `${layout.widths[0]}px`, height: `${layout.heights[0]}px` })
    // The content is as tall as every page together, although only a few are in the DOM.
    expect((first.closest('[data-slot="pdf-viewport"]')?.firstElementChild as HTMLElement).style.height).toBe(
      `${layout.total}px`,
    )
    expect(screen.queryByRole('group', { name: 'Page 50' })).toBeNull()
    expect(first.querySelector('canvas')).not.toBeNull()
  })

  it('fits the page to the reading area without horizontal scrolling at 360 px', () => {
    render(<PdfViewport {...props()} />)
    const box = screen.getByRole('group', { name: 'Page 1' })
    expect(Number.parseInt(box.style.width, 10)).toBeLessThanOrEqual(376 - 16)
    const content = region().firstElementChild as HTMLElement
    expect(Number.parseInt(content.style.width, 10)).toBe(376)
  })

  it('opens at the requested page', () => {
    const onPageChange = vi.fn()
    render(<PdfViewport {...props({ initialPage: 40, onPageChange })} />)
    const layout = computeLayout(sizes(100), 'fit', { availWidth: 376, padTop: 64, padBottom: 112 })
    expect(region().scrollTop).toBe((layout.tops[39] as number) - 64)
    expect(screen.getByRole('group', { name: 'Page 40' })).toBeInTheDocument()
  })

  it('scrolling through 100 pages never holds more than six canvases with pixels', async () => {
    const doc = await open(100)
    const { container } = render(<PdfViewport {...props({ doc })} />)
    const layout = computeLayout(sizes(100), 'fit', { availWidth: 376, padTop: 64, padBottom: 112 })
    let worst = 0
    for (let y = 0; y < layout.total; y += 611) {
      await scrollTo(y)
      await new Promise((r) => setTimeout(r, 0))
      worst = Math.max(worst, liveCanvases(container))
    }
    expect(worst).toBeLessThanOrEqual(6)
    expect(worst).toBeGreaterThan(0)
  })

  it('reports the page in view, and which pages are mounted', async () => {
    const onPageChange = vi.fn()
    const onWindowChange = vi.fn()
    render(<PdfViewport {...props({ onPageChange, onWindowChange })} />)
    const layout = computeLayout(sizes(100), 'fit', { availWidth: 376, padTop: 64, padBottom: 112 })
    await scrollTo((layout.tops[9] as number) - 64)
    expect(onPageChange).toHaveBeenLastCalledWith(10)
    const range = onWindowChange.mock.calls.at(-1)?.[0] as [number, number]
    expect(range[0]).toBeLessThanOrEqual(8)
    expect(range[1]).toBeGreaterThanOrEqual(10)
    expect(range[1] - range[0]).toBeLessThanOrEqual(8)
  })

  it('tells the parent which way the student scrolls', async () => {
    const onScrollDirection = vi.fn()
    render(<PdfViewport {...props({ onScrollDirection })} />)
    await scrollTo(400)
    expect(onScrollDirection).toHaveBeenLastCalledWith('down')
    await scrollTo(100)
    expect(onScrollDirection).toHaveBeenLastCalledWith('up')
  })

  it('jumps on request, again for the same page with a new nonce', async () => {
    const onPageChange = vi.fn()
    const { rerender } = render(<PdfViewport {...props({ onPageChange })} />)
    rerender(<PdfViewport {...props({ onPageChange, jumpTo: { page: 25, nonce: 1 } })} />)
    await waitFor(() => expect(screen.getByRole('group', { name: 'Page 25' })).toBeInTheDocument())
    expect(onPageChange).toHaveBeenLastCalledWith(25)
    await scrollTo(0)
    onPageChange.mockClear()
    rerender(<PdfViewport {...props({ onPageChange, jumpTo: { page: 25, nonce: 1 } })} />)
    expect(onPageChange).not.toHaveBeenCalled()
    rerender(<PdfViewport {...props({ onPageChange, jumpTo: { page: 25, nonce: 2 } })} />)
    await waitFor(() => expect(onPageChange).toHaveBeenCalledWith(25))
  })

  it('zooms by steps through the handle and keeps the page under the top of the area', async () => {
    const onZoomChange = vi.fn()
    const ref = createRef<ViewportHandle>()
    render(<PdfViewport {...props({ ref, onZoomChange })} />)
    act(() => ref.current?.zoomIn())
    // Fit width is about 60%, so one step up is 75%.
    expect(onZoomChange).toHaveBeenLastCalledWith(75)
    act(() => ref.current?.zoomOut())
    expect(onZoomChange).toHaveBeenLastCalledWith(50)
    act(() => ref.current?.zoomFit())
    expect(onZoomChange).toHaveBeenLastCalledWith('fit')
  })

  it('pans inside the area when zoomed: the content is wider than the area and the page does not overflow the document', () => {
    render(<PdfViewport {...props({ zoom: 200 })} />)
    const content = region().firstElementChild as HTMLElement
    expect(Number.parseInt(content.style.width, 10)).toBeGreaterThan(376)
    expect(region().className).toMatch(/overflow-auto/)
    expect(region().className).toMatch(/touch-pan-x/)
  })

  it('zooms with Ctrl and the wheel, and leaves a plain wheel alone', () => {
    const onZoomChange = vi.fn()
    render(<PdfViewport {...props({ onZoomChange })} />)
    const plain = new WheelEvent('wheel', { deltaY: -50, cancelable: true, bubbles: true })
    region().dispatchEvent(plain)
    expect(plain.defaultPrevented).toBe(false)
    expect(onZoomChange).not.toHaveBeenCalled()
    const ctrl = new WheelEvent('wheel', { deltaY: -50, ctrlKey: true, cancelable: true, bubbles: true })
    region().dispatchEvent(ctrl)
    expect(ctrl.defaultPrevented).toBe(true)
    expect(onZoomChange).toHaveBeenCalledTimes(1)
    expect(onZoomChange.mock.calls[0]?.[0]).toBeGreaterThan(60)
  })

  it('zooms with a pinch: a preview while the fingers move, the new zoom when they lift', () => {
    const onZoomChange = vi.fn()
    render(<PdfViewport {...props({ onZoomChange })} />)
    const el = region()
    const down = (id: number, x: number, y: number) =>
      fireEvent.pointerDown(el, { pointerId: id, pointerType: 'touch', clientX: x, clientY: y })
    const move = (id: number, x: number, y: number) =>
      fireEvent.pointerMove(el, { pointerId: id, pointerType: 'touch', clientX: x, clientY: y })
    down(1, 100, 300)
    down(2, 200, 300)
    move(1, 50, 300)
    move(2, 250, 300)
    expect((el.firstElementChild as HTMLElement).style.transform).toMatch(/scale\(/)
    expect(onZoomChange).not.toHaveBeenCalled()
    fireEvent.pointerUp(el, { pointerId: 2, pointerType: 'touch' })
    expect((el.firstElementChild as HTMLElement).style.transform).toBe('')
    const zoom = onZoomChange.mock.calls[0]?.[0]
    expect(typeof zoom).toBe('number')
    expect(zoom).toBeGreaterThan(100)
  })

  it('double tap toggles between fit and magnified', () => {
    const onZoomChange = vi.fn()
    render(<PdfViewport {...props({ onZoomChange })} />)
    const el = region()
    const tap = (t: number) => {
      fireEvent.pointerDown(el, { pointerId: 1, pointerType: 'touch', clientX: 100, clientY: 300, timeStamp: t })
      fireEvent.pointerUp(el, { pointerId: 1, pointerType: 'touch', clientX: 100, clientY: 300, timeStamp: t + 40 })
    }
    tap(1000)
    tap(1150)
    expect(onZoomChange).toHaveBeenLastCalledWith(150)
  })

  it('a tap in the middle toggles the bars, a tap near the edge does not', () => {
    vi.useFakeTimers()
    const onTapMiddle = vi.fn()
    render(<PdfViewport {...props({ onTapMiddle })} />)
    const el = region()
    el.getBoundingClientRect = () => ({
      top: 0,
      left: 0,
      width: 376,
      height: 700,
      right: 376,
      bottom: 700,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    })
    const tap = (y: number, t: number) => {
      fireEvent.pointerDown(el, { pointerId: 1, pointerType: 'touch', clientX: 100, clientY: y, timeStamp: t })
      fireEvent.pointerUp(el, { pointerId: 1, pointerType: 'touch', clientX: 100, clientY: y, timeStamp: t + 30 })
    }
    tap(20, 1000)
    act(() => vi.advanceTimersByTime(500))
    expect(onTapMiddle).not.toHaveBeenCalled()
    tap(350, 5000)
    act(() => vi.advanceTimersByTime(500))
    expect(onTapMiddle).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })

  it('does not disable the browser zoom: no viewport lock, only the reading area handles gestures', () => {
    render(<PdfViewport {...props()} />)
    expect(document.querySelector('meta[name="viewport"]')?.getAttribute('content') ?? '').not.toMatch(
      /user-scalable=no|maximum-scale/,
    )
    expect(region().className).not.toMatch(/touch-none/)
  })

  it('can be reached with the keyboard', () => {
    render(<PdfViewport {...props()} />)
    expect(region()).toHaveAttribute('tabindex', '0')
  })
})
