import type { Overview } from './types'

/** Select value of the "All chapters" option: the whole subject, so no chapter id is sent. */
export const ALL_CHAPTERS = '__all__'
export const ALL_CHAPTERS_LABEL = 'All chapters'

type SubjectsOf = Pick<Overview, 'subjects' | 'electives'>

/**
 * Core papers plus only the elective papers the student chose. The overview lists every paper of the level, including the
 * electives they did not pick; those are not on their syllabus, so no Subject field may offer them.
 */
export function chosenSubjects<T extends SubjectsOf>(data: T | undefined): T['subjects'] {
  if (!data) return []
  const chosen = new Map(data.electives.map((slot) => [slot.key, slot.chosen]))
  return data.subjects.filter((s) => !s.elective_slot || chosen.get(s.elective_slot) === s.id)
}
