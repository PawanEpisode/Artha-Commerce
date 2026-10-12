import { getDocument } from './documents-api'
import { loadPdfjsEngine, type PdfEngine } from './pdf-engine'

/** Width in CSS pixels of a generated cover; the card box is at most 72 px wide, so this stays sharp on 3x screens. */
export const COVER_WIDTH = 240
/** Covers drawn at once; the rest wait their turn so a long library does not open dozens of files together. */
export const MAX_CONCURRENT_COVERS = 2
const MAX_CACHED_COVERS = 80

export interface CoverCandidate {
  status: string
  /** The card is on screen. */
  visible: boolean
  online: boolean
  /** The server's thumbnail is missing or failed to load. */
  needsFallback: boolean
}

/** Only a ready file, on screen, online, with no working server thumbnail. A locked file never gets a preview. */
export const shouldGenerateCover = ({ status, visible, online, needsFallback }: CoverCandidate) =>
  status === 'ready' && visible && online && needsFallback

/** Canvas pixels per PDF point so the first page comes out `COVER_WIDTH` wide. */
export const coverScale = (pageWidth: number) => (pageWidth > 0 ? COVER_WIDTH / pageWidth : 1)

/** Runs at most `max` jobs at once, in the order they were asked for. */
export function createLimiter(max: number) {
  let running = 0
  const waiting: Array<() => void> = []
  const next = () => {
    if (running >= max) return
    const start = waiting.shift()
    if (start) start()
  }
  return <T>(job: () => Promise<T>): Promise<T> =>
    new Promise<T>((resolve, reject) => {
      const start = () => {
        running += 1
        job()
          .then(resolve, reject)
          .finally(() => {
            running -= 1
            next()
          })
      }
      waiting.push(start)
      next()
    })
}

const limit = createLimiter(MAX_CONCURRENT_COVERS)
const covers = new Map<string, string>()
const inflight = new Map<string, Promise<string | null>>()
const failed = new Set<string>()

export const getCachedCover = (id: string): string | null => covers.get(id) ?? null

/** Test seam: forget every generated cover. */
export function resetCoverCache() {
  covers.clear()
  inflight.clear()
  failed.clear()
}

function remember(id: string, url: string) {
  if (covers.size >= MAX_CACHED_COVERS) {
    const oldest = covers.keys().next().value
    if (oldest !== undefined) covers.delete(oldest)
  }
  covers.set(id, url)
}

/** Draws page 1 of the file at its signed URL. Resolves null on any failure; always frees the pdf handle. */
async function drawFirstPage(id: string, engine: PdfEngine | undefined): Promise<string | null> {
  let handle: Awaited<ReturnType<PdfEngine['open']>> | null = null
  try {
    const { file_url: first } = await getDocument(id)
    if (!first) return null
    let current = first
    const impl = engine ?? (await loadPdfjsEngine())
    handle = await impl.open({
      url: {
        get: () => current,
        refresh: async () => {
          current = (await getDocument(id)).file_url ?? current
          return current
        },
      },
      requestPassword: async () => null,
    })
    const size = await handle.getPageSize(1)
    const canvas = globalThis.document.createElement('canvas')
    await handle.getPage(1).render(canvas, { scale: coverScale(size.w) })
    const data = canvas.toDataURL('image/webp', 0.8)
    canvas.width = 0
    canvas.height = 0
    return typeof data === 'string' && data.startsWith('data:image/') ? data : null
  } catch {
    return null
  } finally {
    void handle?.destroy().catch(() => undefined)
  }
}

/**
 * A small first-page image for the document, made once per id and kept in memory for the session. Never rejects: a
 * failure resolves null and is remembered so a card that scrolls in and out does not retry forever.
 */
export function loadCover(id: string, engine?: PdfEngine): Promise<string | null> {
  const cached = covers.get(id)
  if (cached) return Promise.resolve(cached)
  if (failed.has(id)) return Promise.resolve(null)
  const pending = inflight.get(id)
  if (pending) return pending
  const job = limit(() => drawFirstPage(id, engine)).then((url) => {
    inflight.delete(id)
    if (url) remember(id, url)
    else failed.add(id)
    return url
  })
  inflight.set(id, job)
  return job
}
