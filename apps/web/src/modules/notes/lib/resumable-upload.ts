import { ApiError } from '~/lib/api'

import type { ResumableHint } from './document-types'

/** How many parts travel at once, how often one is tried, and how long it waits between tries. */
export const CONCURRENCY = 3
export const ATTEMPTS = 4
export const BACKOFF_MS = 1000
const SIGN_AT_ONCE = 20

export interface ResumableDeps {
  start: (docId: string) => Promise<{ part_size: number; parts: number; done: Array<{ number: number; size: number }> }>
  sign: (docId: string, numbers: number[]) => Promise<{ parts: Array<{ number: number; url: string }> }>
  put: (
    url: string,
    part: Blob,
    options: { signal?: AbortSignal; onProgress?: (loaded: number) => void },
  ) => Promise<void>
  finish: (docId: string, parts: number[]) => Promise<unknown>
  /** `setTimeout`, replaceable so tests need no real clock. */
  wait: (ms: number) => Promise<void>
}

const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

/** Whether trying the same part again could help: a dropped connection, a busy storage, a URL that lapsed. */
export const isRetryable = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 0 || error.status === 403 || error.status === 408 || error.status >= 500)

/**
 * Sends a big file in parts and resends only the ones that failed. Parts already in storage (a retry, a second tab) are
 * skipped. Resolves once storage has joined every part; the caller then confirms the upload like any other. Rejects with the
 * last `ApiError` (status 0 for a network failure), or an `AbortError` when `signal` aborts.
 */
export async function uploadInParts(
  deps: ResumableDeps,
  hint: ResumableHint,
  file: Blob,
  options: { signal?: AbortSignal; onProgress?: (loaded: number, total: number) => void } = {},
): Promise<void> {
  const { signal, onProgress } = options
  const state = await deps.start(hint.document_id)
  const size = state.part_size
  const total = state.parts
  const sent = new Set(state.done.map((p) => p.number))
  const partBytes = (n: number) => Math.min(size, file.size - (n - 1) * size)
  const inFlight = new Map<number, number>()
  let finished = [...sent].reduce((sum, n) => sum + partBytes(n), 0)
  const report = () =>
    onProgress?.(Math.min(file.size, finished + [...inFlight.values()].reduce((a, b) => a + b, 0)), file.size)
  report()

  const pending = Array.from({ length: total }, (_, i) => i + 1).filter((n) => !sent.has(n))
  const queue = [...pending]

  // One URL per part, asked for up front in batches (a URL lives an hour); a part whose URL lapsed asks for its own.
  const urls = new Map<number, string>()
  for (let i = 0; i < pending.length; i += SIGN_AT_ONCE)
    for (const part of (await deps.sign(hint.document_id, pending.slice(i, i + SIGN_AT_ONCE))).parts)
      urls.set(part.number, part.url)
  const urlFor = async (n: number, fresh: boolean): Promise<string> => {
    if (fresh || !urls.has(n)) {
      for (const part of (await deps.sign(hint.document_id, [n])).parts) urls.set(part.number, part.url)
    }
    return urls.get(n) as string
  }

  async function sendOne(n: number) {
    const blob = file.slice((n - 1) * size, (n - 1) * size + partBytes(n))
    let fresh = false
    for (let attempt = 1; ; attempt++) {
      if (signal?.aborted) throw new DOMException('Upload cancelled', 'AbortError')
      try {
        const url = await urlFor(n, fresh)
        await deps.put(url, blob, { signal, onProgress: (loaded) => (inFlight.set(n, loaded), report()) })
        inFlight.delete(n)
        finished += partBytes(n)
        sent.add(n)
        report()
        return
      } catch (error) {
        inFlight.delete(n)
        if (isAbort(error) || signal?.aborted) throw error
        if (!isRetryable(error) || attempt >= ATTEMPTS) throw error
        fresh = error instanceof ApiError && error.status === 403 // the URL lapsed: ask for a new one
        await deps.wait(BACKOFF_MS * 2 ** (attempt - 1))
      }
    }
  }

  async function worker() {
    for (let n = queue.shift(); n !== undefined; n = queue.shift()) await sendOne(n)
  }

  const failure: { error?: unknown } = {}
  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, queue.length) }, () =>
      worker().catch((error: unknown) => {
        failure.error ??= error
        queue.length = 0 // stop handing out parts; the ones in flight finish or fail on their own
      }),
    ),
  )
  if (failure.error !== undefined) throw failure.error
  await deps.finish(
    hint.document_id,
    Array.from({ length: total }, (_, i) => i + 1),
  )
}
