/**
 * The PDF engine adapter. The reader talks to these interfaces only; `pdfjs.ts` is the one file that imports
 * `pdfjs-dist` (ESLint enforces it), so swapping the engine (EmbedPDF, PDFium) touches this folder alone.
 *
 * Conventions: pages are 1-based. Sizes are in PDF points with the page's own `/Rotate` applied ("the page as displayed").
 * Everything positional (text items, links) is normalised to that frame: fractions of width and height, origin top-left.
 * Nothing here is React; nothing here stores a password.
 */
import type { OutlineNode, PageSize } from '../document-types'
import type { Rect } from '../geometry'

export type PdfErrorCode =
  /** The student cancelled the password prompt. */
  | 'password_cancelled'
  /** The file is not a readable PDF (corrupt, truncated beyond repair, wrong type). */
  | 'invalid_pdf'
  /** The signed URL could not be renewed or the object is gone. */
  | 'missing_file'
  /** The network failed or the server answered with an error. */
  | 'network'
  /** The call was cancelled through its `AbortSignal` or the document was destroyed. */
  | 'aborted'
  /** A single page could not be drawn. */
  | 'render_failed'
  | 'unknown'

export class PdfEngineError extends Error {
  constructor(
    public code: PdfErrorCode,
    message?: string,
    public status?: number,
  ) {
    super(message ?? code)
    this.name = 'PdfEngineError'
  }
}

export const isAbort = (error: unknown) =>
  (error instanceof PdfEngineError && error.code === 'aborted') ||
  (error instanceof DOMException && error.name === 'AbortError')

/** The file's signed URL: `get` is the current one, `refresh` asks the API for a new one after a 403 (the URL expired). */
export interface PdfUrlProvider {
  get: () => string
  refresh: () => Promise<string>
}

export type PasswordReason = 'need' | 'incorrect'

export interface OpenOptions {
  url: PdfUrlProvider
  /**
   * Called when the file needs a password (first time `need`, afterwards `incorrect`) with the number of tries so far.
   * Resolve with the text the student typed, or `null` to give up. The engine passes it to the decrypting code and
   * forgets it: it is never stored, logged or sent anywhere else.
   */
  requestPassword: (reason: PasswordReason, attempt: number) => Promise<string | null>
  /** Bytes read so far, only reported while the whole file is downloaded (the server ignored Range requests). */
  onProgress?: (loaded: number, total: number) => void
  signal?: AbortSignal
}

/** One run of text positioned on the page. Offsets index `PdfTextContent.text`. */
export interface LayerItem {
  str: string
  /** Box in the normalised frame. For text: left, top of the line box and its width and height (the font size). */
  x: number
  y: number
  w: number
  h: number
  /** Radians, clockwise on screen, about the top-left corner; 0 for upright text. */
  angle: number
  /** Index of `str[0]` in the page text. */
  start: number
}

export interface PdfTextContent {
  /** The page text: item strings in reading order, a newline after each item that ends a line. Same text on every call. */
  text: string
  items: LayerItem[]
}

export type PdfLink = { kind: 'external'; rect: Rect; url: string } | { kind: 'internal'; rect: Rect; page: number }

export interface RenderOptions {
  /** Pixels of canvas per PDF point (CSS scale times the pixel ratio actually used). */
  scale: number
  signal?: AbortSignal
}

export interface PdfPageHandle {
  readonly pageNumber: number
  /**
   * Draws the page into `canvas`, sizing the canvas to `ceil(pageWidth * scale)` by `ceil(pageHeight * scale)`.
   * Rejects with `PdfEngineError('aborted')` when `signal` aborts (the half-drawn canvas is not usable) and
   * `PdfEngineError('render_failed')` when the page cannot be drawn.
   */
  render: (canvas: HTMLCanvasElement, options: RenderOptions) => Promise<void>
  getText: () => Promise<PdfTextContent>
  /** Link annotations only: external `http`, `https` and `mailto` URLs and jumps inside the file. Never executed. */
  getLinks: () => Promise<PdfLink[]>
  /** Frees what the engine caches for this page (operator list, decoded images). The handle stays usable. */
  release: () => void
}

export interface PdfDocumentHandle {
  readonly pageCount: number
  /** True when the file asked for a password to open. Informational only. */
  readonly wasEncrypted: boolean
  getPageSize: (page: number) => Promise<PageSize>
  /** The file's own outline with 1-based pages, or null when it has none. */
  getOutline: () => Promise<OutlineNode[] | null>
  getPage: (page: number) => PdfPageHandle
  /** The page text without positions, cached. Used by local search. */
  getPageText: (page: number) => Promise<string>
  /**
   * Called once when the file becomes unusable after it was opened (a range could not be read, the connection is gone).
   * Returns the unsubscribe function. The reader then shows the "could not open" state with Retry.
   */
  onFatal: (listener: (error: PdfEngineError) => void) => () => void
  /** Cancels everything in flight and frees the worker's copy of the file. Idempotent. */
  destroy: () => Promise<void>
}

export interface PdfEngine {
  open: (options: OpenOptions) => Promise<PdfDocumentHandle>
}

/** The pdf.js engine, loaded on demand so `pdfjs-dist` and its worker stay out of every chunk but the reader's. */
export const loadPdfjsEngine = async (): Promise<PdfEngine> => (await import('./pdfjs')).createPdfjsEngine()
