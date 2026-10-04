import { createFileRoute, notFound } from '@tanstack/react-router'

import { getCourse } from '~/modules/catalog'
import { CourseDetail } from '~/modules/courses'
import { breadcrumbJsonLd, buildHead } from '~/modules/seo'

export const Route = createFileRoute('/courses/$course/')({
  loader: ({ params }) => {
    const course = getCourse(params.course)
    if (!course) throw notFound()
    return { course }
  },
  head: ({ loaderData }) => {
    if (!loaderData) return {}
    const { course } = loaderData
    const path = `/courses/${course.slug}`
    return buildHead({
      title: `${course.name} (${course.fullName}) Exam Preparation`,
      description: course.description,
      path,
      jsonLd: breadcrumbJsonLd([
        { name: 'Home', path: '/' },
        { name: 'Courses', path: '/courses' },
        { name: course.name, path },
      ]),
    })
  },
  component: function CourseRoute() {
    const { course } = Route.useLoaderData()
    return <CourseDetail course={course} />
  },
})
