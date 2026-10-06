import type { CourseSummary } from '~/modules/personalization'

export function greetingFor(hour: number): string {
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

/** "Good evening, Aarav". Without a name it is just the greeting. */
export function headline(hour: number, firstName: string): string {
  const greeting = greetingFor(hour)
  return firstName ? `${greeting}, ${firstName}` : greeting
}

export interface ExamChip {
  text: string
  /** False when the student still has to set the date: the chip becomes a link to do it. */
  dated: boolean
}

/** "238 days to CMA Final, June 2027", or the nudge to set the date. */
export function examChip(course: CourseSummary | null): ExamChip {
  if (!course) return { text: 'Choose your course', dated: false }
  if (course.days_remaining === null || !course.exam_date) return { text: 'Set your exam date', dated: false }
  const name = [course.course.name, course.level.name].join(' ')
  const when = course.term ? `, ${course.term.name}` : ''
  if (course.days_remaining < 0) return { text: `${name} exam date has passed`, dated: true }
  if (course.days_remaining === 0) return { text: `${name} exam is today`, dated: true }
  const days = course.days_remaining === 1 ? '1 day' : `${course.days_remaining} days`
  return { text: `${days} to ${name}${when}`, dated: true }
}
