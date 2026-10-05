import { progressSentence } from '~/modules/coverage'

export interface CoverageSnapshot {
  courseCode: string
  courseName: string
  levelCode: string
  levelName: string
  percent: number
  chaptersDone: number
  chaptersStarted: number
  chaptersTotal: number
}

export interface StudyViewer {
  signedIn: boolean
  /** False when coverage is switched off for this student. */
  coverageOn: boolean
  snapshot: CoverageSnapshot | null
}

export type StudyLink =
  | { to: '/app/syllabus'; label: string }
  | { to: '/app/onboarding'; label: string; search: { course?: string; level?: string } }
  | { to: '/login'; label: string; search: { next: string } }

export interface StudyPrompt {
  title: string
  body: string
  link: StudyLink
  percent?: number
  progressLabel?: string
}

export function toSnapshot(overview: {
  enrollment: { course: { code: string; name: string }; level: { code: string; name: string } }
  level: { pct_simple: number; chapters_done: number; chapters_started?: number; chapters_total: number }
}): CoverageSnapshot {
  return {
    courseCode: overview.enrollment.course.code.toLowerCase(),
    courseName: overview.enrollment.course.name,
    levelCode: overview.enrollment.level.code.toLowerCase(),
    levelName: overview.enrollment.level.name,
    percent: Math.round(overview.level.pct_simple),
    chaptersDone: overview.level.chapters_done,
    chaptersStarted: overview.level.chapters_started ?? overview.level.chapters_done,
    chaptersTotal: overview.level.chapters_total,
  }
}

const onboardingNext = (course?: string, level?: string) => {
  const params = new URLSearchParams()
  if (course) params.set('course', course)
  if (level) params.set('level', level)
  const query = params.toString()
  return query ? `/app/onboarding?${query}` : '/app/onboarding'
}

const chapterSentence = (s: CoverageSnapshot) => progressSentence(s)

const continuePrompt = (s: CoverageSnapshot, label: string, body?: string): StudyPrompt => ({
  title: `${s.courseName} ${s.levelName}`,
  body: body ?? chapterSentence(s),
  link: { to: '/app/syllabus', label },
  percent: s.percent,
  progressLabel: 'Average progress across chapters',
})

const setupPrompt = (
  signedIn: boolean,
  course?: { slug: string; name: string },
  level?: { slug: string; name: string },
): StudyPrompt => {
  const target = level && course ? `${course.name} ${level.name}` : (course?.name ?? 'your course')
  const title = signedIn ? `Mark your first ${target} chapter` : `Track ${target}`
  const body = signedIn
    ? 'Choose your attempt and tick the chapters you have already finished. Your coverage appears straight away.'
    : 'Sign in, pick your attempt, and tick the chapters you have already finished. You will see your coverage straight away.'
  if (!signedIn) {
    return {
      title,
      body,
      link: {
        to: '/login',
        label: 'Sign in to track chapters',
        search: { next: onboardingNext(course?.slug, level?.slug) },
      },
    }
  }
  return {
    title,
    body,
    link: {
      to: '/app/onboarding',
      label: 'Set up my coverage',
      search: {
        ...(course ? { course: course.slug } : {}),
        ...(level ? { level: level.slug } : {}),
      },
    },
  }
}

const sameCourse = (s: CoverageSnapshot, slug: string) => s.courseCode === slug.toLowerCase()
const sameLevel = (s: CoverageSnapshot, slug: string) => s.levelCode === slug.toLowerCase()

/** The banner on /courses. Null when coverage is switched off. */
export function coursesHomePrompt(viewer: StudyViewer): StudyPrompt | null {
  if (!viewer.coverageOn) return null
  if (viewer.snapshot) return continuePrompt(viewer.snapshot, 'Continue coverage')
  if (!viewer.signedIn) {
    return {
      title: 'Tick a chapter you have already finished',
      body: 'Browse any course below. Sign in when you want that tick to count toward your coverage.',
      link: { to: '/login', label: 'Sign in to track chapters', search: { next: '/app/onboarding' } },
    }
  }
  return setupPrompt(true)
}

/** The banner on a course page. */
export function coursePrompt(viewer: StudyViewer, course: { slug: string; name: string }): StudyPrompt | null {
  if (!viewer.coverageOn) return null
  const snapshot = viewer.snapshot
  if (snapshot && sameCourse(snapshot, course.slug)) return continuePrompt(snapshot, 'Continue coverage')
  if (snapshot) {
    return continuePrompt(
      snapshot,
      'Continue coverage',
      `You are tracking ${snapshot.courseName} ${snapshot.levelName}. ${chapterSentence(snapshot)}`,
    )
  }
  return setupPrompt(viewer.signedIn, course)
}

/** The banner on a level page. */
export function levelPrompt(
  viewer: StudyViewer,
  course: { slug: string; name: string },
  level: { slug: string; name: string },
): StudyPrompt | null {
  if (!viewer.coverageOn) return null
  const snapshot = viewer.snapshot
  if (snapshot && sameCourse(snapshot, course.slug) && sameLevel(snapshot, level.slug)) {
    return continuePrompt(snapshot, 'Tick a chapter')
  }
  if (snapshot && sameCourse(snapshot, course.slug)) {
    return continuePrompt(
      snapshot,
      'Continue coverage',
      `You are tracking ${snapshot.levelName}. ${chapterSentence(snapshot)} This page lists ${level.name}.`,
    )
  }
  if (snapshot) {
    return continuePrompt(
      snapshot,
      'Continue coverage',
      `You are tracking ${snapshot.courseName} ${snapshot.levelName}. ${chapterSentence(snapshot)}`,
    )
  }
  return setupPrompt(viewer.signedIn, course, level)
}

export const promptDestination = (link: StudyLink): 'syllabus' | 'onboarding' | 'login' => {
  if (link.to === '/app/syllabus') return 'syllabus'
  if (link.to === '/app/onboarding') return 'onboarding'
  return 'login'
}
