import { createFileRoute } from '@tanstack/react-router'

import { COURSES_INDEX_REDIRECT_SCRIPT, CoursesIndexContainer, loadCourses } from '~/modules/courses'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/courses/')({
  loader: async () => ({ courses: await loadCourses() }),
  head: () => {
    const head = pageHead('/courses')
    // Signed-in students belong on the home. Guests and crawlers still receive the catalog.
    return { ...head, scripts: [...(head.scripts ?? []), { children: COURSES_INDEX_REDIRECT_SCRIPT }] }
  },
  component: function CoursesRoute() {
    const { courses } = Route.useLoaderData()
    return <CoursesIndexContainer courses={courses} />
  },
})
