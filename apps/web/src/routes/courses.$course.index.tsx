import { createFileRoute, notFound } from '@tanstack/react-router'

import { CourseDetailContainer, loadCourse } from '~/modules/courses'
import { publicPage } from '~/modules/layout'
import { courseHead } from '~/modules/seo'

export const Route = createFileRoute('/courses/$course/')({
  staticData: publicPage,
  loader: async ({ params }) => {
    const course = await loadCourse(params.course, { papers: true })
    if (!course) throw notFound()
    return { course }
  },
  head: ({ loaderData }) => (loaderData ? courseHead(loaderData.course) : {}),
  component: function CourseRoute() {
    const { course } = Route.useLoaderData()
    return <CourseDetailContainer course={course} />
  },
})
