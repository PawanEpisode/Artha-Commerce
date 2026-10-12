/** The enrolment the student studies for: the course and level codes, and the papers on her syllabus. */
export interface StudentPapers {
  course: string
  level: string
  /** `key` of every core paper and of the elective she chose (never the electives she skipped). */
  keys: ReadonlySet<string>
}

const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase()

/**
 * The papers to offer for a course and level: her own (core papers plus the chosen electives) when that level is the one
 * she is enrolled in. For any other level, or without an enrolment (or while it loads or fails), every paper is offered:
 * the picker still works, it just cannot know which papers are hers.
 */
export function papersForStudent<T extends { key: string }>(
  papers: readonly T[],
  course: string,
  level: string,
  student: StudentPapers | null,
): T[] {
  if (!student || student.keys.size === 0 || !same(student.course, course) || !same(student.level, level)) {
    return [...papers]
  }
  return papers.filter((p) => student.keys.has(p.key))
}
