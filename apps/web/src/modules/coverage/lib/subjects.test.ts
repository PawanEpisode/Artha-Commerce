import { describe, expect, it } from 'vitest'

import { chosenSubjects } from './subjects'
import type { Overview } from './types'

const row = (id: string, elective_slot: string | null) => ({ id, key: id, name: id, elective_slot })
const overview = (chosen: string | null) =>
  ({
    subjects: [row('core', null), row('e1', 'slot'), row('e2', 'slot')],
    electives: [{ key: 'slot', chosen }],
  }) as unknown as Pick<Overview, 'subjects' | 'electives'>

describe('chosenSubjects', () => {
  it('keeps core papers and only the chosen elective', () => {
    expect(chosenSubjects(overview('e2')).map((s) => s.id)).toEqual(['core', 'e2'])
  })
  it('hides every elective until one is chosen', () => {
    expect(chosenSubjects(overview(null)).map((s) => s.id)).toEqual(['core'])
  })
  it('is empty without an overview', () => {
    expect(chosenSubjects(undefined)).toEqual([])
  })
})
