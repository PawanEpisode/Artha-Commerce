/** One place for query keys so mutations invalidate exactly what they change. */
export const coverageKeys = {
  all: ['coverage'] as const,
  enrollments: ['coverage', 'enrollments'] as const,
  overview: ['coverage', 'overview'] as const,
  subject: (id: string) => ['coverage', 'subject', id] as const,
  subjects: ['coverage', 'subject'] as const,
  chapter: (id: string) => ['coverage', 'chapter', id] as const,
  due: ['coverage', 'due'] as const,
  continue: ['coverage', 'continue'] as const,
  settings: ['coverage', 'settings'] as const,
}
