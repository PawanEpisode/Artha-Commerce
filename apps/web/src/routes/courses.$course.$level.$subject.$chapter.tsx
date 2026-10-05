import { createFileRoute, notFound } from '@tanstack/react-router'

import { findLevel, loadCourse } from '~/modules/courses'
import { chapterHead } from '~/modules/seo'
import { ChapterView, fetchChapter, ReportIssue } from '~/modules/syllabus'

export const Route = createFileRoute('/courses/$course/$level/$subject/$chapter')({
  loader: async ({ params }) => {
    const course = await loadCourse(params.course)
    const level = course && findLevel(course, params.level)
    if (!course || !level) throw notFound()
    const chapter = await fetchChapter(params.course, params.level, params.subject, params.chapter)
    if (!chapter) throw notFound()
    return { course, level, chapter }
  },
  head: ({ loaderData }) => (loaderData ? chapterHead(loaderData.course, loaderData.level, loaderData.chapter) : {}),
  component: function ChapterRoute() {
    const { course, level, chapter } = Route.useLoaderData()
    return (
      <ChapterView
        courseName={course.name}
        levelName={level.name}
        chapter={chapter}
        report={<ReportIssue nodeType="chapter" nodeId={chapter.id} />}
      />
    )
  },
})
