import { describe, expect, it, vi } from 'vitest'

import { createRangeLoader, RangeLoadError } from './range-loader'

const FILE = Uint8Array.from({ length: 1000 }, (_, i) => i % 251)

interface FakeServer {
  fetchImpl: typeof fetch
  calls: Array<{ url: string; range: string | null }>
}

/** A server over `FILE`. `expired` URLs answer 403. `ignoreRange` always answers 200 with the whole body. */
function server(
  options: { ignoreRange?: boolean; expired?: Set<string>; failNetwork?: number; noContentRange?: boolean } = {},
): FakeServer {
  const calls: FakeServer['calls'] = []
  let failures = options.failNetwork ?? 0
  const fetchImpl = (async (url: string, init?: RequestInit) => {
    const range = (init?.headers as Record<string, string> | undefined)?.Range ?? null
    calls.push({ url, range })
    if (failures > 0) {
      failures -= 1
      throw new TypeError('Failed to fetch')
    }
    if (options.expired?.has(url)) return new Response('expired', { status: 403 })
    const match = range ? /^bytes=(\d+)-(\d*)$/.exec(range) : null
    if (options.ignoreRange || !match)
      return new Response(FILE, { status: 200, headers: { 'Content-Length': String(FILE.length) } })
    const begin = Number(match[1])
    const end = Math.min(FILE.length - 1, match[2] ? Number(match[2]) : FILE.length - 1)
    return new Response(FILE.slice(begin, end + 1), {
      status: 206,
      headers: options.noContentRange ? {} : { 'Content-Range': `bytes ${begin}-${end}/${FILE.length}` },
    })
  }) as typeof fetch
  return { fetchImpl, calls }
}

const urls = (first: string, ...fresh: string[]) => {
  let current = first
  const queue = [...fresh]
  return {
    get: () => current,
    refresh: vi.fn(async () => {
      const next = queue.shift()
      if (!next) throw new Error('no more urls')
      current = next
      return next
    }),
  }
}

describe('range loader', () => {
  it('probes with a Range request and reads later ranges on demand', async () => {
    const s = server()
    const loader = createRangeLoader({ url: urls('u1'), fetchImpl: s.fetchImpl, chunkSize: 100 })
    const source = await loader.open()
    expect(source.kind).toBe('range')
    if (source.kind !== 'range') return
    expect(source.length).toBe(1000)
    expect(source.initial).toEqual(FILE.slice(0, 100))
    expect(s.calls[0]).toEqual({ url: 'u1', range: 'bytes=0-99' })
    const chunk = await source.readRange(300, 450)
    expect(chunk).toEqual(FILE.slice(300, 450))
    expect(s.calls[1]?.range).toBe('bytes=300-449')
  })

  it('renews an expired URL on a 403 and repeats the range once', async () => {
    const s = server({ expired: new Set(['old']) })
    const provider = urls('old', 'new')
    const loader = createRangeLoader({ url: provider, fetchImpl: s.fetchImpl, chunkSize: 100 })
    const source = await loader.open()
    expect(provider.refresh).toHaveBeenCalledTimes(1)
    expect(s.calls.map((c) => c.url)).toEqual(['old', 'new'])
    expect(source.kind).toBe('range')
    // The renewed URL is used from now on, with no further refresh.
    if (source.kind === 'range') await source.readRange(100, 200)
    expect(provider.refresh).toHaveBeenCalledTimes(1)
    expect(s.calls[2]?.url).toBe('new')
  })

  it('renews again when a later range finds the URL expired', async () => {
    const expired = new Set<string>()
    const s = server({ expired })
    const provider = urls('a', 'b')
    const loader = createRangeLoader({ url: provider, fetchImpl: s.fetchImpl, chunkSize: 100 })
    const source = await loader.open()
    expired.add('a')
    if (source.kind !== 'range') throw new Error('expected range')
    expect(await source.readRange(500, 600)).toEqual(FILE.slice(500, 600))
    expect(provider.refresh).toHaveBeenCalledTimes(1)
  })

  it('gives up when the renewed URL is refused too, or cannot be renewed', async () => {
    const both = server({ expired: new Set(['a', 'b']) })
    await expect(createRangeLoader({ url: urls('a', 'b'), fetchImpl: both.fetchImpl }).open()).rejects.toMatchObject({
      kind: 'denied',
      status: 403,
    })
    const none = server({ expired: new Set(['a']) })
    await expect(createRangeLoader({ url: urls('a'), fetchImpl: none.fetchImpl }).open()).rejects.toBeInstanceOf(
      RangeLoadError,
    )
  })

  it('falls back to the whole file, with progress, when the server ignores Range', async () => {
    const s = server({ ignoreRange: true })
    const progress: Array<[number, number]> = []
    const loader = createRangeLoader({
      url: urls('u'),
      fetchImpl: s.fetchImpl,
      onProgress: (l, t) => progress.push([l, t]),
    })
    const source = await loader.open()
    expect(source.kind).toBe('whole')
    if (source.kind === 'whole') expect(source.data).toEqual(FILE)
    expect(progress.at(-1)).toEqual([1000, 1000])
  })

  it('treats a first chunk that is the whole file as whole', async () => {
    const s = server()
    const source = await createRangeLoader({ url: urls('u'), fetchImpl: s.fetchImpl, chunkSize: 5000 }).open()
    expect(source.kind).toBe('whole')
    if (source.kind === 'whole') expect(source.data).toEqual(FILE)
  })

  it('downloads the file again when a 206 carries no usable total', async () => {
    const s = server({ noContentRange: true })
    const source = await createRangeLoader({ url: urls('u'), fetchImpl: s.fetchImpl, chunkSize: 100 }).open()
    expect(source.kind).toBe('whole')
    if (source.kind === 'whole') expect(source.data).toEqual(FILE)
  })

  it('slices the answer when a later range gets a 200', async () => {
    const calls: string[] = []
    let first = true
    const fetchImpl = (async (_u: string, init?: RequestInit) => {
      calls.push((init?.headers as Record<string, string>).Range as string)
      if (first) {
        first = false
        return new Response(FILE.slice(0, 100), { status: 206, headers: { 'Content-Range': 'bytes 0-99/1000' } })
      }
      return new Response(FILE, { status: 200 })
    }) as typeof fetch
    const source = await createRangeLoader({ url: urls('u'), fetchImpl, chunkSize: 100 }).open()
    if (source.kind !== 'range') throw new Error('expected range')
    expect(await source.readRange(10, 20)).toEqual(FILE.slice(10, 20))
  })

  it('names the failure: network, missing, server, aborted', async () => {
    await expect(
      createRangeLoader({ url: urls('u'), fetchImpl: server({ failNetwork: 1 }).fetchImpl }).open(),
    ).rejects.toMatchObject({ kind: 'network' })
    const gone = (async () => new Response('', { status: 404 })) as unknown as typeof fetch
    await expect(createRangeLoader({ url: urls('u'), fetchImpl: gone }).open()).rejects.toMatchObject({
      kind: 'missing',
      status: 404,
    })
    const broken = (async () => new Response('', { status: 503 })) as unknown as typeof fetch
    await expect(createRangeLoader({ url: urls('u'), fetchImpl: broken }).open()).rejects.toMatchObject({
      kind: 'server',
      status: 503,
    })
    const controller = new AbortController()
    const aborting = (async () => {
      controller.abort()
      throw new DOMException('aborted', 'AbortError')
    }) as unknown as typeof fetch
    await expect(
      createRangeLoader({ url: urls('u'), fetchImpl: aborting, signal: controller.signal }).open(),
    ).rejects.toMatchObject({ kind: 'aborted' })
  })
})
