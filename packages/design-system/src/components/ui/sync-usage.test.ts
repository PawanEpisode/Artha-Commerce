import { describe, expect, it } from 'vitest'

import { syncChipText } from './sync-chip'
import { usageLevel } from './usage-bar'

describe('syncChipText', () => {
  it('words every state, with counts where they matter', () => {
    expect(syncChipText('saved')).toBe('Saved')
    expect(syncChipText('saving')).toBe('Saving…')
    expect(syncChipText('offline')).toBe('Offline: saved on this device')
    expect(syncChipText('offline', 3)).toBe('Offline: saved on this device, 3 waiting')
    expect(syncChipText('attention', 1)).toBe('1 needs your attention')
    expect(syncChipText('attention', 2)).toBe('2 need your attention')
  })
})

describe('usageLevel', () => {
  it('is ok below 90 percent, near from 90 and full at the limit', () => {
    expect(usageLevel(0, 500)).toBe('ok')
    expect(usageLevel(449, 500)).toBe('ok')
    expect(usageLevel(450, 500)).toBe('near')
    expect(usageLevel(500, 500)).toBe('full')
    expect(usageLevel(600, 500)).toBe('full')
  })

  it('treats a missing limit as nothing to measure', () => {
    expect(usageLevel(10, 0)).toBe('ok')
  })
})
