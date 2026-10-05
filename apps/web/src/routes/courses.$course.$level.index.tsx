import { createFileRoute, notFound } from '@tanstack/react-router'

import { findLevel, LevelDetailContainer, loadCourse } from '~/modules/courses'
import { levelHead } from '~/modules/seo'
import { fetchLevel, ReportIssue, SubjectList, SyllabusMeta } from '~/modules/syllabus'

export const Route = createFileRoute('/courses/$course/$level/')({
  loader: async ({ params }) => {
    const course = await loadCourse(params.course)
    const level = course && findLevel(course, params.level)
    if (!course || !level) throw notFound()
    // Curated syllabus from the API. Null (not curated yet, or API unreachable) falls back to the static list.
    const syllabus = await fetchLevel(params.course, params.level)
    return { course, level, syllabus: syllabus?.scheme ? syllabus : null }
  },
  head: ({ loaderData }) => {
    if (!loaderData) return {}
    const { course, level, syllabus } = loaderData
    return levelHead(course, level, syllabus ? syllabus.subjects.length : level.subjects.length, Boolean(syllabus))
  },
  component: function LevelRoute() {
    const { course, level, syllabus } = Route.useLoaderData()
    return (
      <LevelDetailContainer
        course={course}
        level={level}
        subjectCount={syllabus?.subjects.length}
        meta={syllabus?.scheme ? <SyllabusMeta scheme={syllabus.scheme} body={course.body} /> : undefined}
        report={syllabus ? <ReportIssue nodeType="level" nodeId={syllabus.id} /> : undefined}
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
