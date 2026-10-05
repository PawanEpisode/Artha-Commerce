import { createFileRoute } from '@tanstack/react-router'

import { CoursesIndex, loadCourses } from '~/modules/courses'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/courses/')({
  loader: async () => ({ courses: await loadCourses() }),
  head: () =>
    buildHead({
      title: 'CA, CS and CMA Courses',
      description:
        'Explore Foundation, Intermediate/Executive and Final/Professional levels for CA, CS and CMA exam preparation.',
      path: '/courses',
    }),
  component: function CoursesRoute() {
    const { courses } = Route.useLoaderData()
    return <CoursesIndex courses={courses} />
  },
})
