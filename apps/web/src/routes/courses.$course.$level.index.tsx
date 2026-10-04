import { createFileRoute, notFound } from '@tanstack/react-router'

import { getCourse, getLevel } from '~/modules/catalog'
import { LevelDetail } from '~/modules/courses'
import { breadcrumbJsonLd, buildHead } from '~/modules/seo'
import { fetchLevel, SubjectList, SyllabusMeta } from '~/modules/syllabus'

export const Route = createFileRoute('/courses/$course/$level/')({
  loader: async ({ params }) => {
    const course = getCourse(params.course)
    const level = getLevel(params.course, params.level)
    if (!course || !level) throw notFound()
    // Curated syllabus from the API. Null (not curated yet, or API unreachable) falls back to the static list.
    const syllabus = await fetchLevel(params.course, params.level)
    return { course, level, syllabus: syllabus?.scheme ? syllabus : null }
  },
  head: ({ loaderData }) => {
    if (!loaderData) return {}
    const { course, level, syllabus } = loaderData
    const path = `/courses/${course.slug}/${level.slug}`
    const count = syllabus ? syllabus.subjects.length : level.subjects.length
    return buildHead({
      title: `${course.name} ${level.name}: Papers and Preparation`,
      description: `All ${count} papers of ${course.name} ${level.name}${syllabus ? ', with chapters and marks weightage' : ''}, plus study planning, mock tests and revision tools.`,
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
    const { course, level, syllabus } = Route.useLoaderData()
    return (
      <LevelDetail
        course={course}
        level={level}
        subjectCount={syllabus?.subjects.length}
        meta={syllabus?.scheme ? <SyllabusMeta scheme={syllabus.scheme} body={course.body} /> : undefined}
        syllabus={
          syllabus ? (
            <SubjectList
              course={course.slug}
              level={level.slug}
              groups={syllabus.groups}
              subjects={syllabus.subjects}
            />
          ) : undefined
        }
      />
    )
  },
})
