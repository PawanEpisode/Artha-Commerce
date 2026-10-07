import { describe, expect, it } from 'vitest'

import { legendChanged, tidyLegend, validateLegend } from './legend-edit'

const base = { y: 'Important', g: 'Formula', b: 'Section', p: 'Doubt', o: 'Example' }

describe('colour legend rules', () => {
  it('accepts five different names of 1 to 24 characters', () => expect(validateLegend(base)).toEqual({}))
  it('rejects empty and over-long names', () => {
    const errors = validateLegend({ ...base, y: '   ', g: 'x'.repeat(25) })
    expect(errors.y).toBe('Give this colour a name.')
    expect(errors.g).toMatch(/24 characters or fewer/)
    expect(validateLegend({ ...base, y: 'x'.repeat(24) })).toEqual({})
  })
  it('rejects the same name twice, ignoring case and spacing, on both colours', () => {
    const errors = validateLegend({ ...base, p: ' formula  ' })
    expect(errors.p).toMatch(/already has this name/)
    expect(errors.g).toMatch(/already has this name/)
  })
  it('tidies spacing and detects change', () => {
    expect(tidyLegend({ ...base, y: '  Very   important ' }).y).toBe('Very important')
    expect(legendChanged(base, base)).toBe(false)
    expect(legendChanged({ ...base, y: 'Key' }, base)).toBe(true)
  })
})
