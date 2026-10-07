import { describe, expect, it } from 'vitest'

import { isLargeDocument } from './large-document'

describe('isLargeDocument', () => {
  it('is large over 25 MB or over 400 pages', () => {
    expect(isLargeDocument(25 * 1024 * 1024, 400)).toBe(false)
    expect(isLargeDocument(25 * 1024 * 1024 + 1, 10)).toBe(true)
    expect(isLargeDocument(1000, 401)).toBe(true)
    expect(isLargeDocument(1000, null)).toBe(false)
  })
})
