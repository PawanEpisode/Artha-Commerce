import { useEffect } from 'react'

import { track } from '~/modules/observability'
import { useBootstrap } from '~/modules/personalization'

import { StudyHome } from '../components/StudyHome'
import { useStudyViewer } from '../hooks/useStudyViewer'
import type { PublicCourse } from '../lib/load'
import { studyHomeView, visibleCourses } from '../lib/visible'
import { CoveragePrompt } from './CoveragePrompt'

/** The home a signed-in student sees: their coverage, and only the course they chose. */
export function StudyHomeContainer({ courses }: { courses: PublicCourse[] }) {
  const { ready, study } = useStudyViewer()
  const { data } = useBootstrap()
  const { view, courseCode } = studyHomeView({
    ready,
    signedIn: study.signedIn,
    courseCode: study.snapshot?.courseCode,
  })
  const shown = visibleCourses(courses, courseCode)
  const listed = view === 'enrolled' && shown.length !== 1 ? 'choose' : view

  useEffect(() => {
    if (listed !== 'enrolled' && listed !== 'choose') return
    track('study_home_viewed', { view: listed, course: courseCode })
  }, [listed, courseCode])

  return (
    <StudyHome
      courses={shown}
      view={listed}
      firstName={data?.first_name || undefined}
      prompt={<CoveragePrompt surface="home" />}
    />
  )
}
