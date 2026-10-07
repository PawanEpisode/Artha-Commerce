import { loadPdfjsEngine, type PdfEngine, PdfEngineError } from './pdf-engine'

/** What the client can tell about a chosen file before anything is sent. */
export interface QuickCheck {
  /** The file does not start with the PDF signature: refused without reading further. */
  notPdf: boolean
  /** Null when the page count could not be read in time, or the file is locked (the server checks again). */
  pages: number | null
  encrypted: boolean
}

const MAGIC = '%PDF-'

/**
 * Reads the page count with the pdf.js engine adapter (never `pdfjs-dist` directly) from a local object URL. Cheap: pdf.js
 * reads the file's trailer, not every page. Anything that goes wrong reads as "unknown pages", because refusing a good PDF
 * for a viewer quirk is worse than letting the server decide; only a missing `%PDF-` signature is a certain no.
 */
export async function quickCheck(
  file: File,
  options: { timeoutMs?: number; loadEngine?: () => Promise<PdfEngine> } = {},
): Promise<QuickCheck> {
  const head = await file.slice(0, MAGIC.length).text()
  if (head !== MAGIC) return { notPdf: true, pages: null, encrypted: false }
  const url = URL.createObjectURL(file)
  const abort = new AbortController()
  const timer = setTimeout(() => abort.abort(), options.timeoutMs ?? 4000)
  try {
    const engine = await (options.loadEngine ?? loadPdfjsEngine)()
    const doc = await engine.open({
      url: { get: () => url, refresh: async () => url },
      // The password is never asked for here: a locked file is accepted and opened later with its own prompt.
      requestPassword: async () => null,
      signal: abort.signal,
    })
    const pages = doc.pageCount
    const encrypted = doc.wasEncrypted
    await doc.destroy()
    return { notPdf: false, pages, encrypted }
  } catch (error) {
    return {
      notPdf: false,
      pages: null,
      encrypted: error instanceof PdfEngineError && error.code === 'password_cancelled',
    }
  } finally {
    clearTimeout(timer)
    URL.revokeObjectURL(url)
  }
}
