import { describe, expect, it } from 'vitest'

import { groupBySection, marksLabel, matchesQuery, pluralize } from './format'

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

describe('groupBySection', () => {
  it('groups consecutive chapters by section and keeps order', () => {
    const groups = groupBySection([
      { id: 1, section: 'Section A' },
      { id: 2, section: 'Section A' },
      { id: 3, section: 'Section B' },
    ])
    expect(groups.map((g) => [g.section, g.items.map((i) => i.id)])).toEqual([
      ['Section A', [1, 2]],
      ['Section B', [3]],
    ])
  })
  it('puts chapters without a section in one unnamed group', () => {
    expect(groupBySection([{ id: 1 }, { id: 2, section: '' }])).toEqual([
      { section: '', items: [{ id: 1 }, { id: 2, section: '' }] },
    ])
  })
})

describe('matchesQuery', () => {
  it('matches case-insensitively on part of the name', () => {
    expect(matchesQuery('Income from Salaries', 'salar')).toBe(true)
    expect(matchesQuery('Income from Salaries', '  SALARIES ')).toBe(true)
    expect(matchesQuery('Income from Salaries', 'gst')).toBe(false)
  })
  it('matches everything for an empty query', () => {
    expect(matchesQuery('Anything', '')).toBe(true)
    expect(matchesQuery('Anything', '   ')).toBe(true)
  })
})
