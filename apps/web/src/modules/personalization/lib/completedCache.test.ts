import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { rememberCompleted, wasCompleted } from './completedCache'

describe('completedCache', () => {
  beforeEach(() => {
    const store = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('is per user and can be cleared', () => {
    expect(wasCompleted('a')).toBe(false)
    rememberCompleted('a', true)
    expect(wasCompleted('a')).toBe(true)
    expect(wasCompleted('b')).toBe(false)
    rememberCompleted('a', false)
    expect(wasCompleted('a')).toBe(false)
  })

  it('treats blocked storage as "not completed"', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
      removeItem: () => {
        throw new Error('blocked')
      },
    })
    expect(() => rememberCompleted('a', true)).not.toThrow()
    expect(wasCompleted('a')).toBe(false)
  })
})
