/**
 * Reads a PDF from a signed URL with HTTP range requests, and renews the URL when it expires.
 *
 *   - probe: `Range: bytes=0-<chunk - 1>`. A 206 answer gives the total size and the first chunk, and the engine then asks
 *     for the byte ranges it needs. A 200 answer means the server ignores Range: the body is read in full with progress
 *     (the whole-file fallback of ERD 6.2).
 *   - a 403 (or 401) means the signed URL expired: `url.refresh()` supplies a new one and the same request is repeated
 *     once. A second refusal is an error.
 * No pdf.js here, so it is unit-tested with a fake `fetch`.
 */
import type { PdfUrlProvider } from './index'

export class RangeLoadError extends Error {
  constructor(
    public kind: 'network' | 'denied' | 'missing' | 'server' | 'aborted',
    public status = 0,
  ) {
    super(`range load failed: ${kind}${status ? ` ${status}` : ''}`)
    this.name = 'RangeLoadError'
  }
}

export interface RangeLoadOptions {
  url: PdfUrlProvider
  fetchImpl?: typeof fetch
  /** Bytes asked for in the probe (the first chunk). Default 256 KiB. */
  chunkSize?: number
  signal?: AbortSignal
  onProgress?: (loaded: number, total: number) => void
}

export type PdfSource =
  | {
      kind: 'range'
      length: number
      /** Bytes 0 to `initial.length - 1`. */
      initial: Uint8Array
      /** Bytes `begin` to `end - 1` (end exclusive). */
      readRange: (begin: number, end: number) => Promise<Uint8Array>
    }
  | { kind: 'whole'; data: Uint8Array }

export const DEFAULT_CHUNK = 256 * 1024
const EXPIRED = new Set([401, 403])

const parseContentRange = (value: string | null): { start: number; end: number; total: number } | null => {
  const match = /^bytes (\d+)-(\d+)\/(\d+|\*)$/.exec(value ?? '')
  if (!match) return null
  return { start: Number(match[1]), end: Number(match[2]), total: match[3] === '*' ? -1 : Number(match[3]) }
}

export function createRangeLoader(options: RangeLoadOptions) {
  const doFetch = options.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args))
  const chunk = options.chunkSize ?? DEFAULT_CHUNK

  /** One request; on an expired URL, renew it and repeat once. */
  async function request(range: string): Promise<Response> {
    const send = async (url: string) => {
      try {
        return await doFetch(url, { headers: { Range: range }, signal: options.signal, credentials: 'omit' })
      } catch (error) {
        if (options.signal?.aborted || (error instanceof DOMException && error.name === 'AbortError'))
          throw new RangeLoadError('aborted')
        throw new RangeLoadError('network')
      }
    }
    let response = await send(options.url.get())
    if (EXPIRED.has(response.status)) {
      let fresh: string
      try {
        fresh = await options.url.refresh()
      } catch {
        throw new RangeLoadError('denied', response.status)
      }
      response = await send(fresh)
      if (EXPIRED.has(response.status)) throw new RangeLoadError('denied', response.status)
    }
    if (response.status === 404 || response.status === 410) throw new RangeLoadError('missing', response.status)
    if (!response.ok) throw new RangeLoadError('server', response.status)
    return response
  }

  async function readAll(response: Response): Promise<Uint8Array> {
    const total = Number(response.headers.get('Content-Length')) || 0
    if (!response.body) {
      const data = new Uint8Array(await response.arrayBuffer())
      options.onProgress?.(data.length, data.length)
      return data
    }
    const reader = response.body.getReader()
    const parts: Uint8Array[] = []
    let loaded = 0
    for (;;) {
      let step: ReadableStreamReadResult<Uint8Array>
      try {
        step = await reader.read()
      } catch {
        throw new RangeLoadError(options.signal?.aborted ? 'aborted' : 'network')
      }
      if (step.done) break
      parts.push(step.value)
      loaded += step.value.length
      options.onProgress?.(loaded, total || loaded)
    }
    const data = new Uint8Array(loaded)
    let at = 0
    for (const part of parts) {
      data.set(part, at)
      at += part.length
    }
    return data
  }

  async function readRange(begin: number, end: number): Promise<Uint8Array> {
    const response = await request(`bytes=${begin}-${end - 1}`)
    if (response.status === 206) return new Uint8Array(await response.arrayBuffer())
    // The server answered 200 to a later range: take the slice we asked for from the whole body.
    return (await readAll(response)).subarray(begin, end)
  }

  async function open(): Promise<PdfSource> {
    const response = await request(`bytes=0-${chunk - 1}`)
    if (response.status !== 206) return { kind: 'whole', data: await readAll(response) }
    const info = parseContentRange(response.headers.get('Content-Range'))
    const initial = new Uint8Array(await response.arrayBuffer())
    // No usable total (`*` or a bad header), or the first chunk already is the whole file: nothing to range over.
    if (!info || info.total <= 0) return { kind: 'whole', data: await readAllFrom(initial) }
    if (initial.length >= info.total) return { kind: 'whole', data: initial }
    return { kind: 'range', length: info.total, initial, readRange }
  }

  /** The total is unknown: fetch the file again without Range. */
  async function readAllFrom(_first: Uint8Array): Promise<Uint8Array> {
    const response = await request('bytes=0-')
    return readAll(response)
  }

  return { open, readRange }
}
