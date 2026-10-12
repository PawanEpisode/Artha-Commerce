import { describe, expect, it } from 'vitest'

import { papersForStudent, type StudentPapers } from './studentPapers'

const papers = [{ key: 'core' }, { key: 'e1' }, { key: 'e2' }]
const student: StudentPapers = { course: 'cma', level: 'final', keys: new Set(['core', 'e2']) }

describe('papersForStudent', () => {
  it('offers core papers and the chosen elective of her own level, not the electives she skipped', () => {
    expect(papersForStudent(papers, 'cma', 'final', student).map((p) => p.key)).toEqual(['core', 'e2'])
  })
  it('matches course and level codes without regard to case', () => {
    expect(papersForStudent(papers, 'CMA', 'Final', student)).toHaveLength(2)
  })
  it('offers every paper of another level or course', () => {
    expect(papersForStudent(papers, 'cma', 'inter', student)).toHaveLength(3)
    expect(papersForStudent(papers, 'ca', 'final', student)).toHaveLength(3)
  })
  it('offers every paper without an enrolment, or before her papers are known', () => {
    expect(papersForStudent(papers, 'cma', 'final', null)).toHaveLength(3)
    expect(papersForStudent(papers, 'cma', 'final', { ...student, keys: new Set() })).toHaveLength(3)
  })
})
