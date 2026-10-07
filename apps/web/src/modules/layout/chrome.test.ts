import { describe, expect, it } from 'vitest'

import { isBareChrome } from './chrome'

describe('isBareChrome', () => {
  it('is true when any matched route asks for the bare chrome', () => {
    expect(isBareChrome([{ staticData: {} }, { staticData: { chrome: 'bare' } }])).toBe(true)
  })
  it('is false for ordinary routes and for no match', () => {
    expect(isBareChrome([{ staticData: {} }])).toBe(false)
    expect(isBareChrome([])).toBe(false)
  })
})
