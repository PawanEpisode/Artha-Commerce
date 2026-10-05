import { describe, expect, it } from 'vitest'

import { playChime, volumeToGain } from './chime'

describe('chime', () => {
  it('maps volume to a gentle gain', () => {
    expect(volumeToGain(0)).toBe(0)
    expect(volumeToGain(100)).toBeCloseTo(0.6)
    expect(volumeToGain(50)).toBeLessThan(volumeToGain(100) / 2)
    expect(volumeToGain(-5)).toBe(0)
    expect(volumeToGain(500)).toBeCloseTo(0.6)
  })

  it('does nothing, without throwing, where there is no audio', () => {
    expect(playChime(80)).toBe(false)
  })
})
