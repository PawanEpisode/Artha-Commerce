import { describe, expect, it } from 'vitest'

import { marksLabel, pluralize } from './format'

describe('marksLabel', () => {
  it('shows a range', () => expect(marksLabel({ marks_min: '5.00', marks_max: '8.00' })).toBe('5 to 8 marks'))
  it('shows a single value', () => expect(marksLabel({ marks_min: null, marks_max: '6' })).toBe('6 marks'))
  it('handles one mark', () => expect(marksLabel({ marks_min: '1', marks_max: '1' })).toBe('1 mark'))
  it('is null without weightage', () => expect(marksLabel({ marks_min: null, marks_max: null })).toBeNull())
})

describe('pluralize', () => {
  it('pluralises', () => {
    expect(pluralize(1, 'chapter')).toBe('1 chapter')
    expect(pluralize(3, 'chapter')).toBe('3 chapters')
  })
})
