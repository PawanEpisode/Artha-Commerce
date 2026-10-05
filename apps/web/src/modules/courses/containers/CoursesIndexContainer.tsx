import { CoursesIndex } from '../components/CoursesIndex'
import { useStudyViewer } from '../hooks/useStudyViewer'
import type { PublicCourse } from '../lib/load'
import { CoveragePrompt } from './CoveragePrompt'

export function CoursesIndexContainer({ courses }: { courses: PublicCourse[] }) {
  const { ready, study } = useStudyViewer()
  return (
    <CoursesIndex
      courses={courses}
      activeCourseCode={ready ? study.snapshot?.courseCode : null}
      prompt={<CoveragePrompt surface="home" />}
    />
  )
}
