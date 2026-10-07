import { describe, expect, it } from 'vitest'

import { createFakeEngine } from './fake-engine'
import { searchLocally } from './local-search'

async function doc(pages: string[]) {
  const engine = createFakeEngine({ pages: pages.map((text) => ({ text })) })
  return engine.open({ url: { get: () => 'u', refresh: async () => 'u' }, requestPassword: async () => null })
}

describe('searchLocally', () => {
  it('lists hits page by page with a snippet', async () => {
    const d = await doc(['ITC is blocked', 'nothing here', 'ITC again and ITC'])
    const r = await searchLocally(d, 'itc')
    expect(r.hits.map((h) => h.page)).toEqual([1, 3, 3])
    expect(r.hits[0]?.snippet).toContain('ITC')
    expect(r.truncated).toBe(false)
  })

  it('stops at the limit and says so', async () => {
    const d = await doc(Array.from({ length: 10 }, () => 'ITC ITC ITC'))
    const r = await searchLocally(d, 'itc', { limit: 4 })
    expect(r.hits).toHaveLength(4)
    expect(r.truncated).toBe(true)
  })

  it('reports progress and can be cancelled', async () => {
    const d = await doc(['a ITC', 'b', 'c', 'd'])
    const seen: number[] = []
    await searchLocally(d, 'itc', { onProgress: (done) => seen.push(done) })
    expect(seen).toEqual([1, 2, 3, 4])
    const controller = new AbortController()
    controller.abort()
    expect((await searchLocally(d, 'itc', { signal: controller.signal })).aborted).toBe(true)
  })

  it('goes on past a page that cannot be read', async () => {
    const d = await doc(['ITC', 'ITC'])
    const original = d.getPageText.bind(d)
    d.getPageText = async (p: number) => {
      if (p === 1) throw new Error('boom')
      return original(p)
    }
    expect((await searchLocally(d, 'itc')).hits.map((h) => h.page)).toEqual([2])
  })
})
