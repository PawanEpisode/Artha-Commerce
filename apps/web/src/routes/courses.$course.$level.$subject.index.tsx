import { createFileRoute, notFound } from '@tanstack/react-router'

import { getCourse, getLevel } from '~/modules/catalog'
import { breadcrumbJsonLd, buildHead } from '~/modules/seo'
import { fetchSubject, ReportIssue, SubjectView } from '~/modules/syllabus'

export const Route = createFileRoute('/courses/$course/$level/$subject/')({
  loader: async ({ params }) => {
    const course = getCourse(params.course)
    const level = getLevel(params.course, params.level)
    if (!course || !level) throw notFound()
    const subject = await fetchSubject(params.course, params.level, params.subject)
    if (!subject) throw notFound()
    return { course, level, subject }
  },
  head: ({ loaderData }) => {
    if (!loaderData) return {}
    const { course, level, subject } = loaderData
    const path = `/courses/${course.slug}/${level.slug}/${subject.key}`
    return buildHead({
      title: `${subject.name}: ${course.name} ${level.name} Syllabus and Chapters`,
      description: `${subject.name} for ${course.name} ${level.name}: ${subject.chapters.length} chapters${subject.total_marks ? `, ${subject.total_marks} marks` : ''}, with marks weightage and topics.`,
      path,
      jsonLd: [
        breadcrumbJsonLd([
          { name: 'Home', path: '/' },
          { name: 'Courses', path: '/courses' },
          { name: course.name, path: `/courses/${course.slug}` },
          { name: level.name, path: `/courses/${course.slug}/${level.slug}` },
          { name: subject.name, path },
        ]),
        {
          '@context': 'https://schema.org',
          '@type': 'Course',
          name: `${subject.name} (${course.name} ${level.name})`,
          description: `Syllabus of ${subject.name} for ${course.name} ${level.name}.`,
          provider: { '@type': 'Organization', name: course.bodyFullName },
          hasPart: subject.chapters.map((c) => ({ '@type': 'Course', name: c.name })),
        },
      ],
    })
  },
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
