import { describe, expect, it } from 'vitest'

import { isLite } from './lite'

describe('isLite', () => {
  it('follows the setting when the student chose', () => {
    expect(isLite('on', {})).toBe(true)
    expect(isLite('off', { saveData: true, effectiveType: '2g' })).toBe(false)
  })
  it('auto turns on for Data Saver and for 2g', () => {
    expect(isLite('auto', { saveData: true })).toBe(true)
    expect(isLite('auto', { effectiveType: '2g' })).toBe(true)
    expect(isLite('auto', { effectiveType: 'slow-2g' })).toBe(true)
  })
  it('auto stays off on a normal connection, or when the browser says nothing, or before settings load', () => {
    expect(isLite('auto', { effectiveType: '4g' })).toBe(false)
    expect(isLite('auto', {})).toBe(false)
    expect(isLite(undefined, {})).toBe(false)
  })
})
