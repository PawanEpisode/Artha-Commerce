export type StudyHomeView = 'guest' | 'pending' | 'choose' | 'enrolled'

/** The signed-in home. Guests are not shown this view; a chosen course replaces the catalog. */
export function studyHomeView(input: { ready: boolean; signedIn: boolean; courseCode?: string | null }): {
  view: StudyHomeView
  courseCode: string | null
} {
  if (!input.ready) return { view: input.signedIn ? 'pending' : 'guest', courseCode: null }
  if (!input.signedIn || !input.courseCode) {
    return { view: input.signedIn ? 'choose' : 'guest', courseCode: null }
  }
  return { view: 'enrolled', courseCode: input.courseCode.toLowerCase() }
}

/** Keep the enrolled course when it is in the list. Otherwise leave the catalog intact. */
export function visibleCourses<T extends { slug: string }>(courses: readonly T[], courseCode: string | null): T[] {
  if (!courseCode) return [...courses]
  const mine = courses.filter((course) => course.slug === courseCode)
  return mine.length > 0 ? mine : [...courses]
}
