import { describe, expect, it } from 'vitest'

import { contextLabel } from './contextLabel'

describe('contextLabel', () => {
  it('names the subject and chapter', () => {
    expect(contextLabel('Taxation', 'GST')).toBe('Taxation · GST')
  })
  it('reads a subject with no chapter as "All chapters", not blank', () => {
    expect(contextLabel('Taxation', undefined)).toBe('Taxation · All chapters')
  })
  it('is undefined when nothing is known', () => {
    expect(contextLabel(undefined, undefined)).toBeUndefined()
  })
})
