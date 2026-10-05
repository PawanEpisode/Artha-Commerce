import { CourseDetail } from '../components/CourseDetail'
import type { PublicCourse } from '../lib/load'
import { CoveragePrompt } from './CoveragePrompt'

export function CourseDetailContainer({ course }: { course: PublicCourse }) {
  return (
    <CourseDetail
      course={course}
      prompt={<CoveragePrompt surface="course" course={{ slug: course.slug, name: course.name }} />}
    />
  )
}
