import { fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { resetCoverCache } from '../../lib/document-cover'
import { createFakeEngine } from '../../lib/pdf-engine/fake-engine'
import { makeDocument } from '../../lib/testing-documents'
import { DocumentCover } from './DocumentCover'

const getDocument = vi.hoisted(() => vi.fn())
vi.mock('../../lib/documents-api', () => ({ getDocument }))

const GENERATED = 'data:image/webp;base64,AAAA'

/** Reports the element as on screen as soon as it is observed. */
class VisibleObserver {
  constructor(private callback: IntersectionObserverCallback) {}
  observe(target: Element) {
    this.callback([{ isIntersecting: true, target } as IntersectionObserverEntry], this as never)
  }
  unobserve() {}
  disconnect() {}
}

const doc = (overrides = {}) => makeDocument({ cover_url: null, ...overrides })
const image = () => document.querySelector('img')

beforeEach(() => {
  resetCoverCache()
  getDocument.mockResolvedValue({ file_url: 'https://storage.example/a.pdf?token=1' })
  vi.stubGlobal('IntersectionObserver', VisibleObserver)
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue(GENERATED)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  getDocument.mockReset()
})

describe('DocumentCover', () => {
  it('shows the server thumbnail and does not open the file', () => {
    const engine = createFakeEngine()
    render(<DocumentCover doc={doc({ cover_url: 'https://cdn.example/cover.webp' })} engine={engine} />)
    expect(image()).toHaveAttribute('src', 'https://cdn.example/cover.webp')
    expect(engine.opens).toBe(0)
  })

  it('draws the first page when there is no server thumbnail', async () => {
    const engine = createFakeEngine()
    render(<DocumentCover doc={doc()} engine={engine} />)
    await waitFor(() => expect(image()).toHaveAttribute('src', GENERATED))
    expect(engine.opens).toBe(1)
    expect(engine.renders).toHaveLength(1)
    expect(engine.renders[0]?.page).toBe(1)
    expect(engine.documents[0]?.destroyed).toBe(true)
  })

  it('draws the first page when the server thumbnail fails to load, then keeps the generated one', async () => {
    const engine = createFakeEngine()
    render(<DocumentCover doc={doc({ cover_url: 'https://cdn.example/expired.webp' })} engine={engine} />)
    fireEvent.error(image() as HTMLImageElement)
    await waitFor(() => expect(image()).toHaveAttribute('src', GENERATED))
  })

  it('keeps the file icon when the first page cannot be drawn', async () => {
    const engine = createFakeEngine({ pages: [{ failRenders: Infinity }] })
    const { container } = render(<DocumentCover doc={doc()} engine={engine} />)
    await waitFor(() => expect(engine.opens).toBe(1))
    await waitFor(() => expect(engine.documents[0]?.destroyed).toBe(true))
    expect(image()).toBeNull()
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('never opens a locked file and keeps its lock badge', () => {
    const engine = createFakeEngine()
    const { container } = render(<DocumentCover doc={doc({ status: 'needs_password' })} engine={engine} />)
    expect(engine.opens).toBe(0)
    expect(image()).toBeNull()
    expect(container.querySelectorAll('svg')).toHaveLength(2)
  })

  it('waits until the card is on screen', async () => {
    class IdleObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    vi.stubGlobal('IntersectionObserver', IdleObserver)
    const engine = createFakeEngine()
    render(<DocumentCover doc={doc()} engine={engine} />)
    await new Promise((r) => setTimeout(r, 10))
    expect(engine.opens).toBe(0)
  })

  it('does not start a preview for a compact card', async () => {
    const engine = createFakeEngine()
    render(<DocumentCover doc={doc()} compact engine={engine} />)
    await new Promise((r) => setTimeout(r, 10))
    expect(engine.opens).toBe(0)
  })
})
