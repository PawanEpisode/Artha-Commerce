import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PdfPageHandle } from '../../lib/pdf-engine'
import { createFakeEngine } from '../../lib/pdf-engine/fake-engine'
import { PdfPage, type PdfPageProps } from './PdfPage'
import { usePdfPageContext } from './PdfPageContext'

async function pageHandle(options: Parameters<typeof createFakeEngine>[0] = {}, page = 1): Promise<PdfPageHandle> {
  const engine = createFakeEngine({ pageCount: 3, ...options })
  const doc = await engine.open({
    url: { get: () => 'u', refresh: async () => 'u' },
    requestPassword: async () => null,
  })
  return doc.getPage(page)
}

const baseProps = (handle: PdfPageHandle | null, over: Partial<PdfPageProps> = {}): PdfPageProps => ({
  page: 1,
  handle,
  width: 360,
  height: 509,
  scale: 0.6,
  pageW: 595,
  pageH: 842,
  live: true,
  tone: 'original',
  ...over,
})

describe('PdfPage', () => {
  it('has its final size before anything is drawn and draws a live page', async () => {
    const onDrawn = vi.fn()
    const handle = await pageHandle()
    render(<PdfPage {...baseProps(handle, { onDrawn })} />)
    const box = screen.getByRole('group', { name: 'Page 1' })
    expect(box).toHaveStyle({ width: '360px', height: '509px' })
    await waitFor(() => expect(onDrawn).toHaveBeenCalledWith(1))
    const canvas = box.querySelector('canvas') as HTMLCanvasElement
    expect(canvas.width).toBeGreaterThan(0)
    expect(box).toHaveAttribute('data-state', 'drawn')
  })

  it('holds no pixels when off screen, and frees them when a page leaves', async () => {
    const handle = await pageHandle()
    const { rerender, container } = render(<PdfPage {...baseProps(handle)} />)
    await waitFor(() => expect(container.querySelector('canvas')?.width).toBeGreaterThan(0))
    const canvas = container.querySelector('canvas') as HTMLCanvasElement
    rerender(<PdfPage {...baseProps(handle, { live: false })} />)
    // The element stays (so its size can be zeroed, which frees the memory) but holds no pixels.
    expect(container.querySelector('canvas')).toBe(canvas)
    expect(canvas.width).toBe(0)
    expect(canvas.height).toBe(0)
    expect(screen.getByRole('group', { name: 'Page 1' })).toHaveStyle({ width: '360px', height: '509px' })
  })

  it('shows the cover as a quick first paint until the sharp page is drawn', async () => {
    const handle = await pageHandle({ renderDelayMs: 30 })
    const { container } = render(<PdfPage {...baseProps(handle, { placeholderSrc: 'https://cover.example/1.webp' })} />)
    expect(container.querySelector('img')).toHaveAttribute('src', 'https://cover.example/1.webp')
    await waitFor(() => expect(container.querySelector('img')).toBeNull())
  })

  it('shows a per-page error with Retry, and draws after retrying', async () => {
    const handle = await pageHandle({ pages: [{ failRenders: 1 }, {}, {}] })
    render(<PdfPage {...baseProps(handle)} />)
    expect(await screen.findByText('This page could not be drawn.')).toBeInTheDocument()
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Retry' })))
    await waitFor(() => expect(screen.queryByText('This page could not be drawn.')).not.toBeInTheDocument())
    expect(screen.getByRole('group', { name: 'Page 1' })).toHaveAttribute('data-state', 'drawn')
  })

  it('says "not available offline" when the page cannot load offline', async () => {
    const handle = await pageHandle({ pages: [{ failRenders: Infinity }] })
    render(<PdfPage {...baseProps(handle, { offline: true })} />)
    expect(await screen.findByText('This page is not available offline.')).toBeInTheDocument()
  })

  it('exposes the page text as a real layer a screen reader can read, and hides the canvas from it', async () => {
    const handle = await pageHandle({ pages: [{ text: 'Input tax credit is blocked' }] })
    const { container } = render(<PdfPage {...baseProps(handle)} />)
    const layer = await waitFor(() => {
      const el = container.querySelector('[data-slot="text-layer"]')
      expect(el).not.toBeNull()
      return el as HTMLElement
    })
    expect(layer).toHaveTextContent('Input tax credit is blocked')
    expect(layer.querySelectorAll('[data-start]').length).toBe(5)
    expect(container.querySelector('canvas')).toHaveAttribute('aria-hidden', 'true')
  })

  it('labels the canvas of a page without text', async () => {
    const handle = await pageHandle()
    render(<PdfPage {...baseProps(handle, { useNativeText: false })} />)
    expect(await screen.findByRole('img', { name: /Page 1, an image without selectable text/ })).toBeInTheDocument()
  })

  it('draws search hits and marks the current one', async () => {
    const handle = await pageHandle({ pages: [{ text: 'ITC is blocked. ITC again.' }] })
    const { container } = render(<PdfPage {...baseProps(handle, { query: 'itc', activeIndex: 1 })} />)
    await waitFor(() => expect(container.querySelectorAll('[data-hit]').length).toBe(2))
    expect(container.querySelectorAll('[data-hit="active"]').length).toBe(1)
  })

  it('uses OCR words for the text layer of a scan', async () => {
    const handle = await pageHandle()
    const ocrContent = {
      text: 'blocked credits',
      items: [
        { str: 'blocked', x: 0.1, y: 0.1, w: 0.1, h: 0.01, angle: 0, start: 0 },
        { str: 'credits', x: 0.25, y: 0.1, w: 0.1, h: 0.01, angle: 0, start: 8 },
      ],
    }
    const { container } = render(<PdfPage {...baseProps(handle, { ocrContent, useNativeText: false })} />)
    const layer = container.querySelector('[data-slot="text-layer"]')
    expect(layer).toHaveAttribute('data-kind', 'ocr')
    expect(layer).toHaveTextContent('blocked credits')
  })

  it('renders links that report a click instead of navigating', async () => {
    const handle = await pageHandle({
      pages: [
        {
          links: [
            { kind: 'external', rect: [0.1, 0.1, 0.2, 0.02], url: 'https://www.icai.org/x' },
            { kind: 'internal', rect: [0.1, 0.2, 0.2, 0.02], page: 3 },
          ],
        },
      ],
    })
    const onLink = vi.fn()
    render(<PdfPage {...baseProps(handle, { onLink })} />)
    const external = await screen.findByRole('link', { name: 'Link to www.icai.org' })
    expect(external).toHaveAttribute('rel', 'noopener noreferrer')
    expect(external).toHaveAttribute('target', '_blank')
    fireEvent.click(external)
    expect(onLink).toHaveBeenCalledWith(expect.objectContaining({ kind: 'external', url: 'https://www.icai.org/x' }))
    fireEvent.click(screen.getByRole('link', { name: 'Go to page 3' }))
    expect(onLink).toHaveBeenCalledWith(expect.objectContaining({ kind: 'internal', page: 3 }))
  })

  it('has slots for the annotation layer, with the page context', async () => {
    const handle = await pageHandle()
    function Probe({ id }: { id: string }) {
      const ctx = usePdfPageContext()
      return <i data-testid={id}>{`${ctx.page}:${ctx.width}x${ctx.height}:${ctx.scale}:${ctx.tone}`}</i>
    }
    render(
      <PdfPage {...baseProps(handle, { tone: 'night', marks: <Probe id="marks" /> })}>
        <Probe id="overlay" />
      </PdfPage>,
    )
    expect(screen.getByTestId('marks')).toHaveTextContent('1:360x509:0.6:night')
    expect(screen.getByTestId('overlay')).toHaveTextContent('1:360x509:0.6:night')
    expect(screen.getByRole('group', { name: 'Page 1' })).toHaveAttribute('data-page-tone', 'night')
  })
})
