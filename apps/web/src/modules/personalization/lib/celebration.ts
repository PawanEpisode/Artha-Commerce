import type { CourseSummary } from './types'

/** "Aarav, CMA Final June 2027 is set up. 238 days to go." Parts the student has not given are left out. */
export function celebrationMessage(firstName: string, course: CourseSummary | null): string {
  const who = firstName ? `${firstName}, ` : ''
  if (!course) return `${who}your workspace is ready.`.replace(/^./, (c) => c.toUpperCase())
  const name = [course.course.name, course.level.name, course.term?.name].filter(Boolean).join(' ')
  const days =
    course.days_remaining !== null && course.days_remaining > 0
      ? ` ${course.days_remaining} ${course.days_remaining === 1 ? 'day' : 'days'} to go.`
      : ''
  return `${who}${name} is set up.${days}`
}

const key = (version: number) => `onboarding-celebrated-v${version}`

/** Once per version per browser tab session (the server's `completed_at` covers the rest). Storage may be blocked. */
export function celebrationSeen(version: number): boolean {
  try {
    return sessionStorage.getItem(key(version)) === '1'
  } catch {
    return false
  }
}

export function markCelebrated(version: number): void {
  try {
    sessionStorage.setItem(key(version), '1')
  } catch {
    // Private mode: the celebration may repeat once. Harmless.
  }
}
