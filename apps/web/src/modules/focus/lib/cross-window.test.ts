import { describe, expect, it } from 'vitest'

import { alertClaimKey, claimAlert, otherWindowVisible, reportWindowVisible } from './cross-window'

function memoryStore(seed: Record<string, string> = {}) {
  const data = new Map(Object.entries(seed))
  return {
    get length() {
      return data.size
    },
    key: (i: number) => [...data.keys()][i] ?? null,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
    keys: () => [...data.keys()],
  }
}

describe('alertClaimKey', () => {
  it('is artha:alerted:<client_id>:<version>, with a suffix for the target alert', () => {
    expect(alertClaimKey('k1', 7)).toBe('artha:alerted:k1:7')
    expect(alertClaimKey('k1', 7, 'target')).toBe('artha:alerted:k1:7:target')
    expect(alertClaimKey('k1', undefined)).toBe('artha:alerted:k1:0')
  })
})

describe('claimAlert', () => {
  it('lets the first window claim a phase end and refuses every later one', () => {
    const store = memoryStore()
    expect(claimAlert('artha:alerted:k:1', 1000, store)).toBe(true)
    expect(claimAlert('artha:alerted:k:1', 1001, store)).toBe(false)
    expect(claimAlert('artha:alerted:k:2', 1002, store)).toBe(true)
  })

  it('forgets claims older than a day', () => {
    const day = 24 * 60 * 60 * 1000
    const store = memoryStore({ 'artha:alerted:old:1': '0', 'artha:alerted:junk:1': 'x', other: 'keep' })
    claimAlert('artha:alerted:new:1', day + 1, store)
    expect(store.keys().sort()).toEqual(['artha:alerted:new:1', 'other'])
  })

  it('plays anyway where storage is missing or throws: a double chime beats silence', () => {
    expect(claimAlert('k', 0, null)).toBe(true)
    const broken = {
      length: 0,
      key: () => null,
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => undefined,
      removeItem: () => undefined,
    }
    expect(claimAlert('k', 0, broken)).toBe(true)
  })
})

describe('window visibility', () => {
  it('sees another window that said it was visible recently, never itself', () => {
    const store = memoryStore()
    reportWindowVisible('a', true, 1000, store)
    expect(otherWindowVisible('a', 1000, store)).toBe(false)
    expect(otherWindowVisible('b', 1000, store)).toBe(true)
  })

  it('stops seeing a window once it says it is hidden, or when its record is stale', () => {
    const store = memoryStore()
    reportWindowVisible('a', true, 1000, store)
    expect(otherWindowVisible('b', 1000 + 30_000, store)).toBe(false)
    reportWindowVisible('a', true, 40_000, store)
    reportWindowVisible('a', false, 41_000, store)
    expect(otherWindowVisible('b', 41_000, store)).toBe(false)
  })

  it('is false without storage', () => {
    expect(otherWindowVisible('b', 0, null)).toBe(false)
  })
})
