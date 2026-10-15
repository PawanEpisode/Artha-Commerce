import { describe, expect, it } from 'vitest'

import { pyqSearchSchema } from './types'

describe('pyqSearchSchema', () => {
  it('parses empty search params', () => {
    const res = pyqSearchSchema.parse({})
    expect(res).toEqual({})
  })

  it('parses valid search filters', () => {
    const res = pyqSearchSchema.parse({
      course: 'cma',
      level: 'cma_intermediate',
      subject: 'taxation',
      term: 'dec_2023',
      q: 'Direct Tax',
    })
    expect(res.course).toBe('cma')
    expect(res.level).toBe('cma_intermediate')
    expect(res.subject).toBe('taxation')
    expect(res.term).toBe('dec_2023')
    expect(res.q).toBe('Direct Tax')
  })
})
