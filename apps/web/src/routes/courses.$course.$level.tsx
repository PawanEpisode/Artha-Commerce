import { createFileRoute, notFound } from '@tanstack/react-router'

import { getCourse, getLevel } from '~/modules/catalog'
import { LevelDetail } from '~/modules/courses'
import { breadcrumbJsonLd, buildHead } from '~/modules/seo'

export const Route = createFileRoute('/courses/$course/$level')({
  loader: ({ params }) => {
    const course = getCourse(params.course)
    const level = getLevel(params.course, params.level)
    if (!course || !level) throw notFound()
    return { course, level }
  },
  head: ({ loaderData }) => {
    if (!loaderData) return {}
    const { course, level } = loaderData
    const path = `/courses/${course.slug}/${level.slug}`
    return buildHead({
      title: `${course.name} ${level.name}: Papers and Preparation`,
      description: `All ${level.subjects.length} papers of ${course.name} ${level.name}, with study planning, mock tests and revision tools.`,
      path,
      jsonLd: breadcrumbJsonLd([
        { name: 'Home', path: '/' },
        { name: 'Courses', path: '/courses' },
        { name: course.name, path: `/courses/${course.slug}` },
        { name: level.name, path },
      ]),
    })
  },
  component: function LevelRoute() {
    const { course, level } = Route.useLoaderData()
    return <LevelDetail course={course} level={level} />
  },
})
