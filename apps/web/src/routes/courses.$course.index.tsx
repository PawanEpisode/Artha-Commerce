import { createFileRoute, notFound } from '@tanstack/react-router'

import { CourseDetailContainer, loadCourse } from '~/modules/courses'
import { breadcrumbJsonLd, buildHead, courseOgPath } from '~/modules/seo'

export const Route = createFileRoute('/courses/$course/')({
  loader: async ({ params }) => {
    const course = await loadCourse(params.course, { papers: true })
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
      image: courseOgPath(course.slug),
      imageAlt: `${course.fullName} (${course.name}) exam preparation`,
      jsonLd: breadcrumbJsonLd([
        { name: 'Home', path: '/' },
        { name: 'Courses', path: '/courses' },
        { name: course.name, path },
      ]),
    })
  },
  component: function CourseRoute() {
    const { course } = Route.useLoaderData()
    return <CourseDetailContainer course={course} />
  },
})
