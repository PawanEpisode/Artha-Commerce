import { createFileRoute, notFound } from '@tanstack/react-router'

import { findLevel, loadCourse } from '~/modules/courses'
import { subjectHead } from '~/modules/seo'
import { fetchSubject, ReportIssue, SubjectView } from '~/modules/syllabus'

export const Route = createFileRoute('/courses/$course/$level/$subject/')({
  loader: async ({ params }) => {
    const course = await loadCourse(params.course)
    const level = course && findLevel(course, params.level)
    if (!course || !level) throw notFound()
    const subject = await fetchSubject(params.course, params.level, params.subject)
    if (!subject) throw notFound()
    return { course, level, subject }
  },
  head: ({ loaderData }) => (loaderData ? subjectHead(loaderData.course, loaderData.level, loaderData.subject) : {}),
  component: function SubjectRoute() {
    const { course, level, subject } = Route.useLoaderData()
    return (
      <SubjectView
        courseName={course.name}
        levelName={level.name}
        body={course.body}
        subject={subject}
        report={<ReportIssue nodeType="subject" nodeId={subject.id} />}
      />
    )
  },
})
