import { describe, expect, it, vi } from 'vitest'

import { clearAllLocalData, registerLocalDataClearer } from './local-data'

describe('local data clearers', () => {
  it('runs every clearer with the user id and reports the ones that failed', async () => {
    const ok = vi.fn()
    registerLocalDataClearer('a-ok', ok)
    registerLocalDataClearer('b-broken', () => {
      throw new Error('blocked')
    })
    const after = vi.fn()
    registerLocalDataClearer('c-after', after)
    const failed = await clearAllLocalData('u1')
    expect(ok).toHaveBeenCalledWith('u1')
    expect(after).toHaveBeenCalledWith('u1')
    expect(failed).toEqual(['b-broken'])
  })

  it('replaces a clearer registered twice under one name', async () => {
    const first = vi.fn()
    const second = vi.fn()
    registerLocalDataClearer('same', first)
    registerLocalDataClearer('same', second)
    await clearAllLocalData('u2')
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledWith('u2')
  })
})
