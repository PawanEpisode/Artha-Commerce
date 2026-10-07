/**
 * The pdf.js implementation of the engine adapter, and the only file in the app that imports `pdfjs-dist`.
 *
 * Decisions (see also apps/web/scripts/copy-pdfjs-assets.mjs):
 *  - Worker: bundled by Vite through a `?url` import, so parsing and decoding stay off the main thread and the worker
 *    file is only fetched when a PDF is opened. `pdfjs-dist` itself is imported dynamically inside `createPdfjsEngine`.
 *  - Build: the `legacy` build of pdf.js. The modern build calls `Map.prototype.getOrInsertComputed`, which Chrome before 145,
 *    Safari before 26 and many Android WebViews lack (found in the browser check: every page failed to render on
 *    Chromium 141). The legacy build ships the polyfills and costs nothing else.
 *  - Transport: our own range transport (`range-loader.ts`) so an expired signed URL is renewed and retried, and a server
 *    that ignores Range falls back to one download with progress. `disableAutoFetch` keeps pdf.js from reading the
 *    rest of a 500-page file in the background.
 *  - Untrusted files: pdf.js only runs a PDF's JavaScript when a viewer wires up its scripting manager and sandbox
 *    (`pdf.sandbox.mjs`). This adapter never does, and never creates an annotation or form layer, so scripting is off by
 *    construction (ERD 7). 5.x removed the `isEvalSupported` and `enableScripting` document options; there is nothing to set.
 *    Links are returned as data (`getLinks`) and opened by the reader after a confirm.
 *  - Data files (`/pdfjs/...`, copied into `public/` at dev and build): predefined CMaps, the standard 14 fonts and the
 *    JBIG2 / JPEG 2000 / colour decoders, fetched on demand. Embedded fonts, which is how Devanagari PDFs ship, need none.
 *  - Annotation drawing is `ENABLE` (appearance streams of the file's own marks on the canvas, no form widgets).
 */
import type * as PdfJsModule from 'pdfjs-dist'
import type { PDFDocumentLoadingTask, PDFDocumentProxy, PDFPageProxy, RenderTask } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'

import type { OutlineNode, PageSize } from '../document-types'
import type { Rect } from '../geometry'
import {
  isAbort,
  type OpenOptions,
  type PasswordReason,
  type PdfDocumentHandle,
  type PdfEngine,
  PdfEngineError,
  type PdfLink,
  type PdfPageHandle,
  type PdfTextContent,
  type RenderOptions,
} from './index'
import { createRangeLoader, type PdfSource, RangeLoadError } from './range-loader'
import { buildTextModel, pageTextOf, runFromPdfItem } from './text-items'

type PdfJs = typeof PdfJsModule

const RANGE_CHUNK = 256 * 1024
const DATA_BASE = '/pdfjs/'
const ALLOWED_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])
/** `AnnotationMode.ENABLE` in pdf.js: draw the file's own annotation appearances, no interactive forms. */
const ANNOTATION_MODE_ENABLE = 1

const dataUrl = (name: string) =>
  new URL(`${DATA_BASE}${name}/`, globalThis.location?.origin ?? 'http://localhost').href

function mapError(error: unknown): PdfEngineError {
  if (error instanceof PdfEngineError) return error
  if (error instanceof RangeLoadError) {
    if (error.kind === 'aborted') return new PdfEngineError('aborted')
    if (error.kind === 'missing' || error.kind === 'denied')
      return new PdfEngineError('missing_file', undefined, error.status)
    return new PdfEngineError('network', undefined, error.status)
  }
  const name = (error as { name?: string } | null)?.name
  if (name === 'InvalidPDFException' || name === 'FormatError') return new PdfEngineError('invalid_pdf')
  if (name === 'MissingPDFException') return new PdfEngineError('missing_file')
  if (name === 'AbortException' || name === 'RenderingCancelledException' || name === 'AbortError')
    return new PdfEngineError('aborted')
  if (name === 'UnexpectedResponseException' || name === 'ResponseException') return new PdfEngineError('network')
  return new PdfEngineError('unknown', error instanceof Error ? error.message : undefined)
}

const toRect = (x1: number, y1: number, x2: number, y2: number, w: number, h: number): Rect => {
  const left = Math.min(x1, x2)
  const top = Math.min(y1, y2)
  return [left / w, top / h, Math.abs(x2 - x1) / w, Math.abs(y2 - y1) / h]
}

class PdfjsPage implements PdfPageHandle {
  private proxy: Promise<PDFPageProxy> | null = null
  private text: Promise<PdfTextContent> | null = null
  private links: Promise<PdfLink[]> | null = null
  private task: RenderTask | null = null

  constructor(
    private doc: PdfjsDocument,
    readonly pageNumber: number,
  ) {}

  private page() {
    this.proxy ??= this.doc.proxy.getPage(this.pageNumber)
    return this.proxy
  }

  async render(canvas: HTMLCanvasElement, { scale, signal }: RenderOptions) {
    if (signal?.aborted) throw new PdfEngineError('aborted')
    try {
      const page = await this.page()
      const viewport = page.getViewport({ scale })
      canvas.width = Math.ceil(viewport.width)
      canvas.height = Math.ceil(viewport.height)
      this.task?.cancel()
      const task = page.render({ canvas, viewport, annotationMode: ANNOTATION_MODE_ENABLE })
      this.task = task
      const cancel = () => task.cancel()
      signal?.addEventListener('abort', cancel, { once: true })
      try {
        await task.promise
      } finally {
        signal?.removeEventListener('abort', cancel)
        if (this.task === task) this.task = null
      }
    } catch (error) {
      if (signal?.aborted) throw new PdfEngineError('aborted')
      const mapped = mapError(error)
      throw mapped.code === 'unknown' ? new PdfEngineError('render_failed', mapped.message) : mapped
    }
  }

  getText(): Promise<PdfTextContent> {
    this.text ??= (async () => {
      const page = await this.page()
      const viewport = page.getViewport({ scale: 1 })
      const content = await page.getTextContent()
      const runs = content.items.flatMap((item) => ('str' in item ? [runFromPdfItem(item, viewport.transform)] : []))
      return buildTextModel(runs, viewport.width, viewport.height)
    })().catch((error) => {
      this.text = null
      throw mapError(error)
    })
    return this.text
  }

  getLinks(): Promise<PdfLink[]> {
    this.links ??= (async () => {
      const page = await this.page()
      const viewport = page.getViewport({ scale: 1 })
      const annotations = await page.getAnnotations({ intent: 'display' })
      const out: PdfLink[] = []
      for (const a of annotations) {
        if (a.subtype !== 'Link' || !Array.isArray(a.rect)) continue
        const [rx1 = 0, ry1 = 0, rx2 = 0, ry2 = 0] = a.rect as number[]
        const [x1 = 0, y1 = 0] = viewport.convertToViewportPoint(rx1, ry1) as number[]
        const [x2 = 0, y2 = 0] = viewport.convertToViewportPoint(rx2, ry2) as number[]
        const rect = toRect(x1, y1, x2, y2, viewport.width, viewport.height)
        const url = (a.url ?? a.unsafeUrl) as string | undefined
        if (url) {
          try {
            if (ALLOWED_PROTOCOLS.has(new URL(url).protocol)) out.push({ kind: 'external', rect, url })
          } catch {
            // A relative or malformed URL is not something we open.
          }
        } else if (a.dest) {
          const target = await this.doc.pageOfDestination(a.dest)
          if (target) out.push({ kind: 'internal', rect, page: target })
        }
      }
      return out
    })().catch(() => {
      this.links = null
      return []
    })
    return this.links
  }

  release() {
    this.task?.cancel()
    this.task = null
    void this.proxy?.then((p) => p.cleanup()).catch(() => undefined)
  }
}

class PdfjsDocument implements PdfDocumentHandle {
  private pages = new Map<number, PdfjsPage>()
  private texts = new Map<number, Promise<string>>()
  private sizes = new Map<number, Promise<PageSize>>()
  private fatal: PdfEngineError | null = null
  private listeners = new Set<(error: PdfEngineError) => void>()
  private destroyed = false

  constructor(
    readonly proxy: PDFDocumentProxy,
    private task: PDFDocumentLoadingTask,
    readonly wasEncrypted: boolean,
    private abort: AbortController,
  ) {}

  get pageCount() {
    return this.proxy.numPages
  }

  /** Called by the range transport when a range could not be read after its retries: the file is unusable. */
  fail(error: PdfEngineError) {
    if (this.fatal || this.destroyed) return
    this.fatal = error
    for (const listener of this.listeners) listener(error)
    void this.destroy()
  }

  onFatal(listener: (error: PdfEngineError) => void) {
    this.listeners.add(listener)
    if (this.fatal) listener(this.fatal)
    return () => this.listeners.delete(listener)
  }

  getPage(page: number): PdfPageHandle {
    let handle = this.pages.get(page)
    if (!handle) {
      handle = new PdfjsPage(this, page)
      this.pages.set(page, handle)
    }
    return handle
  }

  getPageSize(page: number): Promise<PageSize> {
    let size = this.sizes.get(page)
    if (!size) {
      size = this.proxy
        .getPage(page)
        .then((p) => {
          const v = p.getViewport({ scale: 1 })
          return { w: v.width, h: v.height }
        })
        .catch((error) => {
          this.sizes.delete(page)
          throw mapError(error)
        })
      this.sizes.set(page, size)
    }
    return size
  }

  async pageOfDestination(dest: unknown): Promise<number | null> {
    try {
      const explicit = typeof dest === 'string' ? await this.proxy.getDestination(dest) : (dest as unknown[])
      const ref = explicit?.[0]
      if (typeof ref === 'number') return ref + 1
      if (ref && typeof ref === 'object')
        return (await this.proxy.getPageIndex(ref as { num: number; gen: number })) + 1
    } catch {
      // A broken destination is skipped, not fatal.
    }
    return null
  }

  async getOutline(): Promise<OutlineNode[] | null> {
    let raw: Awaited<ReturnType<PDFDocumentProxy['getOutline']>>
    try {
      raw = await this.proxy.getOutline()
    } catch {
      return null
    }
    if (!raw || raw.length === 0) return null
    let budget = 2000
    const convert = async (nodes: typeof raw): Promise<OutlineNode[]> => {
      const out: OutlineNode[] = []
      for (const node of nodes ?? []) {
        if (budget-- <= 0) break
        const page = node.dest ? ((await this.pageOfDestination(node.dest)) ?? 0) : 0
        out.push({ title: String(node.title ?? '').trim() || 'Untitled', page, children: await convert(node.items) })
      }
      return out
    }
    return convert(raw)
  }

  getPageText(page: number): Promise<string> {
    let cached = this.texts.get(page)
    if (!cached) {
      cached = this.proxy
        .getPage(page)
        .then((p) => p.getTextContent())
        .then((content) =>
          pageTextOf(content.items.flatMap((item) => ('str' in item ? [{ str: item.str, hasEOL: item.hasEOL }] : []))),
        )
        .catch((error) => {
          this.texts.delete(page)
          throw mapError(error)
        })
      this.texts.set(page, cached)
    }
    return cached
  }

  async destroy() {
    if (this.destroyed) return
    this.destroyed = true
    this.abort.abort()
    for (const page of this.pages.values()) page.release()
    this.pages.clear()
    try {
      await this.task.destroy()
    } catch {
      // Already gone.
    }
  }
}

async function loadPdfjs(): Promise<PdfJs> {
  const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs')
  if (pdfjs.GlobalWorkerOptions.workerSrc !== workerUrl) pdfjs.GlobalWorkerOptions.workerSrc = workerUrl
  return pdfjs
}

/** pdf.js's `onPassword` reasons: 1 asks for a password, 2 says the one given was wrong. */
const reasonOf = (code: number): PasswordReason => (code === 2 ? 'incorrect' : 'need')

export function createPdfjsEngine(): PdfEngine {
  return {
    async open(options: OpenOptions): Promise<PdfDocumentHandle> {
      const pdfjs = await loadPdfjs()
      const abort = new AbortController()
      const forward = () => abort.abort()
      options.signal?.addEventListener('abort', forward, { once: true })
      if (options.signal?.aborted) abort.abort()

      let source: PdfSource
      try {
        source = await createRangeLoader({
          url: options.url,
          chunkSize: RANGE_CHUNK,
          signal: abort.signal,
          onProgress: options.onProgress,
        }).open()
      } catch (error) {
        throw mapError(error)
      }

      // Filled once the document exists so a failed range can fail it.
      let current: PdfjsDocument | null = null
      const loader = createRangeLoader({ url: options.url, chunkSize: RANGE_CHUNK, signal: abort.signal })
      const common = {
        rangeChunkSize: RANGE_CHUNK,
        disableAutoFetch: true,
        disableStream: true,
        cMapUrl: dataUrl('cmaps'),
        cMapPacked: true,
        standardFontDataUrl: dataUrl('standard_fonts'),
        wasmUrl: dataUrl('wasm'),
        iccUrl: dataUrl('iccs'),
        useSystemFonts: true,
        verbosity: 0,
      }

      let task: PDFDocumentLoadingTask
      if (source.kind === 'whole') {
        task = pdfjs.getDocument({ ...common, data: source.data })
      } else {
        const range = source
        class Transport extends pdfjs.PDFDataRangeTransport {
          requestDataRange(begin: number, end: number) {
            const clampedEnd = Math.min(end, range.length)
            // Up to three tries with a short pause: a flaky mobile connection often recovers in a second.
            const attempt = async (n: number): Promise<void> => {
              try {
                const chunk = await loader.readRange(begin, clampedEnd)
                this.onDataRange(begin, chunk)
              } catch (error) {
                const mapped = mapError(error)
                if (mapped.code === 'aborted') return
                if (n < 3 && mapped.code === 'network') {
                  await new Promise((r) => setTimeout(r, 500 * 2 ** n))
                  return attempt(n + 1)
                }
                current?.fail(mapped)
              }
            }
            void attempt(0)
          }
          abort() {}
        }
        task = pdfjs.getDocument({ ...common, range: new Transport(range.length, range.initial) })
      }

      let tries = 0
      let cancelled = false
      task.onPassword = (update: (password: string | Error) => void, code: number) => {
        const reason = reasonOf(code)
        tries += 1
        options
          .requestPassword(reason, tries)
          .then((password) => {
            if (password === null) {
              cancelled = true
              void task.destroy()
            } else update(password)
          })
          .catch(() => {
            cancelled = true
            void task.destroy()
          })
      }

      try {
        const proxy = await task.promise
        const document = new PdfjsDocument(proxy, task, tries > 0, abort)
        current = document
        return document
      } catch (error) {
        if (cancelled) throw new PdfEngineError('password_cancelled')
        if (isAbort(error) || abort.signal.aborted) throw new PdfEngineError('aborted')
        throw mapError(error)
      } finally {
        options.signal?.removeEventListener('abort', forward)
      }
    },
  }
}
