import { describe, expect, it } from 'vitest'

import { prefillSelection } from './prefill'

const courses = [
  { code: 'CA', levels: [{ code: 'foundation' }, { code: 'intermediate' }] },
  { code: 'CS', levels: [{ code: 'executive' }] },
]

describe('prefillSelection', () => {
  it('matches public slugs to the codes the radios use', () => {
    expect(prefillSelection(courses, 'ca', 'intermediate')).toEqual({ course: 'CA', level: 'intermediate' })
  })

  it('keeps the course when the level is unknown', () => {
    expect(prefillSelection(courses, 'cs', 'final')).toEqual({ course: 'CS', level: '' })
  })

  it('returns empty when the course is unknown', () => {
    expect(prefillSelection(courses, 'acca', 'foundation')).toEqual({ course: '', level: '' })
    expect(prefillSelection(courses)).toEqual({ course: '', level: '' })
  })
})
