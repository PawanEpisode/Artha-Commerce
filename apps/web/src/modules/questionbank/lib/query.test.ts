import { describe, expect, it } from 'vitest'

import { kindLabel } from './labels'
import { buildQuestionQuery } from './query'

describe('buildQuestionQuery', () => {
  it('sends kind as the API `kinds` filter', () => {
    expect(buildQuestionQuery({ kind: 'mcq_multi' }).get('kinds')).toBe('mcq_multi')
    expect(buildQuestionQuery({ kind: 'mcq_multi' }).has('kind')).toBe(false)
  })

  it('turns one year into an inclusive range and maps the term', () => {
    const q = buildQuestionQuery({ year: 2024, term: 'may' })
    expect(q.get('year_from')).toBe('2024')
    expect(q.get('year_to')).toBe('2024')
    expect(q.get('term_codes')).toBe('may')
  })

  it('omits empty params', () => {
    expect(buildQuestionQuery({}).toString()).toBe('')
  })
})

describe('kindLabel', () => {
  it('never prints the raw enum', () => {
    expect(kindLabel('mcq_multi')).toBe('MCQ Multiple Choice')
    expect(kindLabel('some_new_kind')).toBe('Some new kind')
  })
})
