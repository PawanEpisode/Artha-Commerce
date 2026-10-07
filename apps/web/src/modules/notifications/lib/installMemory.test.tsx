import { beforeEach, describe, expect, it, vi } from 'vitest'

import { addDeviceRounds, deviceRounds, lastOfferedAt, markOffered } from './installMemory'

beforeEach(() => localStorage.clear())

describe('installMemory', () => {
  it('counts finished rounds on this device', () => {
    expect(deviceRounds()).toBe(0)
    expect(addDeviceRounds(1)).toBe(1)
    expect(addDeviceRounds(2)).toBe(3)
    expect(deviceRounds()).toBe(3)
  })

  it('ignores nonsense: negative counts and a damaged value', () => {
    addDeviceRounds(-4)
    expect(deviceRounds()).toBe(0)
    localStorage.setItem('artha:install:rounds', 'many')
    expect(deviceRounds()).toBe(0)
  })

  it('remembers when the offer was last shown', () => {
    expect(lastOfferedAt()).toBeNull()
    markOffered(1_700_000_000_000)
    expect(lastOfferedAt()).toBe(1_700_000_000_000)
  })

  it('does not break where storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(deviceRounds()).toBe(0)
    expect(() => markOffered(1)).not.toThrow()
    vi.restoreAllMocks()
  })
})
