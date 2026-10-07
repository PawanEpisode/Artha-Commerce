/**
 * An in-memory `PdfEngine` for tests (and stories): no worker, no canvas drawing, deterministic. Not imported by app code.
 * Options let a test make the file encrypted, make a page fail to draw, slow things down, or fail the open.
 */
import type { OutlineNode, PageSize } from '../document-types'
import {
  type OpenOptions,
  type PdfDocumentHandle,
  type PdfEngine,
  PdfEngineError,
  type PdfLink,
  type PdfPageHandle,
  type PdfTextContent,
} from './index'

export interface FakePage {
  w?: number
  h?: number
  /** Words of the page; laid out in rows of ten on a grid. */
  text?: string
  links?: PdfLink[]
  /** Number of renders that fail before one succeeds; `Infinity` never succeeds. */
  failRenders?: number
}

export interface FakeEngineOptions {
  pages?: FakePage[]
  /** Number of pages when `pages` is not given (each 595 x 842, text "Page N"). */
  pageCount?: number
  outline?: OutlineNode[] | null
  /** When set the file is encrypted: `open` asks for this password. */
  password?: string
  /** Rejects `open` with this error. */
  openError?: PdfEngineError
  openDelayMs?: number
  renderDelayMs?: number
}

export interface FakeEngine extends PdfEngine {
  opens: number
  passwordsAsked: number
  /** Canvases currently holding pixels (width > 0), the "live canvas" count tests assert on. */
  liveCanvases: () => number
  renders: Array<{ page: number; scale: number }>
  /** Every document handle opened, to call `fail` on or inspect. */
  documents: FakeDocument[]
}

/** Lays words out in a grid so selection and search tests have boxes to work with. */
export function fakeTextContent(text: string, pageW = 595, pageH = 842): PdfTextContent {
  const words = text.split(/\s+/).filter(Boolean)
  const items: PdfTextContent['items'] = []
  let out = ''
  words.forEach((word, i) => {
    const row = Math.floor(i / 10)
    const col = i % 10
    items.push({
      str: word,
      x: (40 + col * 50) / pageW,
      y: (60 + row * 16) / pageH,
      w: (word.length * 6) / pageW,
      h: 12 / pageH,
      angle: 0,
      start: out.length,
    })
    out += word + (col === 9 || i === words.length - 1 ? '\n' : ' ')
  })
  return { text: out, items }
}

class FakePageHandle implements PdfPageHandle {
  private failures: number
  constructor(
    private engine: FakeEngineImpl,
    private doc: FakeDocument,
    readonly pageNumber: number,
    private spec: FakePage,
  ) {
    this.failures = spec.failRenders ?? 0
  }

  async render(canvas: HTMLCanvasElement, { scale, signal }: { scale: number; signal?: AbortSignal }) {
    await sleep(this.engine.options.renderDelayMs ?? 0)
    if (signal?.aborted || this.doc.destroyed) throw new PdfEngineError('aborted')
    if (this.failures > 0) {
      this.failures -= 1
      throw new PdfEngineError('render_failed')
    }
    const size = await this.doc.getPageSize(this.pageNumber)
    canvas.width = Math.ceil(size.w * scale)
    canvas.height = Math.ceil(size.h * scale)
    this.engine.renders.push({ page: this.pageNumber, scale })
  }

  async getText() {
    const size = await this.doc.getPageSize(this.pageNumber)
    return fakeTextContent(this.spec.text ?? `Page ${this.pageNumber}`, size.w, size.h)
  }

  async getLinks() {
    return this.spec.links ?? []
  }

  release() {}
}

export class FakeDocument implements PdfDocumentHandle {
  destroyed = false
  private listeners = new Set<(error: PdfEngineError) => void>()
  private handles = new Map<number, FakePageHandle>()
  constructor(
    private engine: FakeEngineImpl,
    private pages: FakePage[],
    readonly wasEncrypted: boolean,
  ) {}

  get pageCount() {
    return this.pages.length
  }

  async getPageSize(page: number): Promise<PageSize> {
    const spec = this.pages[page - 1]
    if (!spec) throw new PdfEngineError('unknown', 'no such page')
    return { w: spec.w ?? 595, h: spec.h ?? 842 }
  }

  async getOutline() {
    return this.engine.options.outline ?? null
  }

  getPage(page: number): PdfPageHandle {
    let handle = this.handles.get(page)
    if (!handle) {
      handle = new FakePageHandle(this.engine, this, page, this.pages[page - 1] ?? {})
      this.handles.set(page, handle)
    }
    return handle
  }

  async getPageText(page: number) {
    return (await this.getPage(page).getText()).text
  }

  onFatal(listener: (error: PdfEngineError) => void) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  /** Test hook: the connection is gone. */
  fail(error = new PdfEngineError('network')) {
    for (const listener of this.listeners) listener(error)
  }

  async destroy() {
    this.destroyed = true
  }
}

const sleep = (ms: number) => (ms > 0 ? new Promise((r) => setTimeout(r, ms)) : Promise.resolve())

class FakeEngineImpl implements FakeEngine {
  opens = 0
  passwordsAsked = 0
  renders: Array<{ page: number; scale: number }> = []
  documents: FakeDocument[] = []
  constructor(readonly options: FakeEngineOptions) {}

  liveCanvases() {
    return Array.from(globalThis.document?.querySelectorAll('canvas') ?? []).filter((c) => c.width > 0).length
  }

  async open(open: OpenOptions): Promise<PdfDocumentHandle> {
    this.opens += 1
    await sleep(this.options.openDelayMs ?? 0)
    if (open.signal?.aborted) throw new PdfEngineError('aborted')
    if (this.options.openError) throw this.options.openError
    const pages = this.options.pages ?? Array.from({ length: this.options.pageCount ?? 3 }, () => ({}))
    let encrypted = false
    if (this.options.password !== undefined) {
      encrypted = true
      let reason: 'need' | 'incorrect' = 'need'
      for (let attempt = 1; ; attempt++) {
        this.passwordsAsked += 1
        const given = await open.requestPassword(reason, attempt)
        if (given === null) throw new PdfEngineError('password_cancelled')
        if (given === this.options.password) break
        reason = 'incorrect'
      }
    }
    const doc = new FakeDocument(this, pages, encrypted)
    this.documents.push(doc)
    return doc
  }
}

export function createFakeEngine(options: FakeEngineOptions = {}): FakeEngine {
  return new FakeEngineImpl(options)
}
