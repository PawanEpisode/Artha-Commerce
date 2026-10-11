import { describe, expect, it } from 'vitest'

import { hasFooter, isBareChrome, publicPage } from './chrome'

describe('isBareChrome', () => {
  it('is true when any matched route asks for the bare chrome', () => {
    expect(isBareChrome([{ staticData: {} }, { staticData: { chrome: 'bare' } }])).toBe(true)
  })
  it('is false for ordinary routes and for no match', () => {
    expect(isBareChrome([{ staticData: {} }])).toBe(false)
    expect(isBareChrome([])).toBe(false)
  })
})

describe('hasFooter', () => {
  it('is false by default, so workspace and any new page have no footer', () => {
    expect(hasFooter([{ staticData: {} }, { staticData: {} }])).toBe(false)
    expect(hasFooter([])).toBe(false)
  })
  it('is true when a matched route is a public page', () => {
    expect(hasFooter([{ staticData: {} }, { staticData: publicPage }])).toBe(true)
  })
  it('is never true for a bare route', () => {
    expect(hasFooter([{ staticData: { footer: true, chrome: 'bare' } }])).toBe(false)
  })
})
