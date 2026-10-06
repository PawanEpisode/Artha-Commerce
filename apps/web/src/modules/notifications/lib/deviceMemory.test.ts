import { afterEach, describe, expect, it, vi } from 'vitest'

import { forgetDeviceId, markSynced, rememberDeviceId, rememberedDeviceId, syncedRecently } from './deviceMemory'

function stubStorage(store: Record<string, string> = {}) {
  vi.stubGlobal('window', {
    localStorage: {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => void (store[k] = v),
      removeItem: (k: string) => void delete store[k],
    },
  })
  return store
}

afterEach(() => vi.unstubAllGlobals())

describe('device memory', () => {
  it('remembers and forgets the device id', () => {
    stubStorage()
    expect(rememberedDeviceId()).toBeNull()
    rememberDeviceId('dev-1')
    expect(rememberedDeviceId()).toBe('dev-1')
    forgetDeviceId()
    expect(rememberedDeviceId()).toBeNull()
  })

  it('knows when a refresh ran recently', () => {
    stubStorage()
    expect(syncedRecently(1_000_000, 500)).toBe(false)
    markSynced(1_000_000)
    expect(syncedRecently(1_000_400, 500)).toBe(true)
    expect(syncedRecently(1_000_600, 500)).toBe(false)
  })

  it('works, without storing, when storage is blocked', () => {
    vi.stubGlobal('window', {
      get localStorage(): never {
        throw new Error('blocked')
      },
    })
    expect(() => rememberDeviceId('x')).not.toThrow()
    expect(rememberedDeviceId()).toBeNull()
    expect(syncedRecently(10, 5)).toBe(false)
    expect(() => markSynced(1)).not.toThrow()
  })

  it('works when there is no window at all', () => {
    expect(rememberedDeviceId()).toBeNull()
    expect(() => forgetDeviceId()).not.toThrow()
  })
})
