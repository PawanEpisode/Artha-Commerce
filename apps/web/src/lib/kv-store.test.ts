import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it } from 'vitest'

import { createKvDatabase } from './kv-store'

const db = createKvDatabase('kv-test', 1, ['a', 'b'])
const a = db.store<{ n: number }>('a')
const b = db.store<string>('b')

beforeEach(async () => {
  db.reset()
  await a.clear()
  await b.clear()
})

describe('kv store', () => {
  it('stores, reads, lists and removes values by key', async () => {
    await a.put('x', { n: 1 })
    await a.put('y', { n: 2 })
    expect(await a.get('x')).toEqual({ n: 1 })
    expect((await a.all()).map((v) => v.n).sort()).toEqual([1, 2])
    await a.remove('x')
    expect(await a.get('x')).toBeUndefined()
  })

  it('keeps stores apart and survives a fresh connection (a reload)', async () => {
    await b.put('k', 'v')
    db.reset()
    expect(await b.get('k')).toBe('v')
    expect(await a.all()).toEqual([])
  })

  it('reads as empty, never throws, when a key is missing', async () => {
    expect(await a.get('nope')).toBeUndefined()
  })
})
