/** Match a public course or level slug to the code the onboarding radios use. */
export function prefillSelection(
  courses: { code: string; levels: { code: string }[] }[],
  wantedCourse?: string,
  wantedLevel?: string,
): { course: string; level: string } {
  const course = courses.find((c) => c.code.toLowerCase() === wantedCourse?.toLowerCase())
  if (!course) return { course: '', level: '' }
  const level = course.levels.find((l) => l.code.toLowerCase() === wantedLevel?.toLowerCase())
  return { course: course.code, level: level?.code ?? '' }
}
