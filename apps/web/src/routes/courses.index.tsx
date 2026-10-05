import { createFileRoute } from '@tanstack/react-router'

import { CoursesIndexContainer, loadCourses } from '~/modules/courses'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/courses/')({
  loader: async () => ({ courses: await loadCourses() }),
  head: () => pageHead('/courses'),
  component: function CoursesRoute() {
    const { courses } = Route.useLoaderData()
    return <CoursesIndexContainer courses={courses} />
  },
})
