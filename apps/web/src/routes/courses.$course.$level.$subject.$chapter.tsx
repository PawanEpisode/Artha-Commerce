import { createFileRoute, notFound } from '@tanstack/react-router'

import { findLevel, loadCourse } from '~/modules/courses'
import { breadcrumbJsonLd, buildHead, chapterOgPath } from '~/modules/seo'
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
  head: ({ loaderData }) => {
    if (!loaderData) return {}
    const { course, level, chapter } = loaderData
    const path = `/courses/${course.slug}/${level.slug}/${chapter.subject.key}/${chapter.key}`
    return buildHead({
      title: `${chapter.name}: ${chapter.subject.name}, ${course.name} ${level.name}`,
      description: `${chapter.name} in ${chapter.subject.name} (${course.name} ${level.name}): ${chapter.topics.length} topics and marks weightage, with a way to track your progress.`,
      path,
      image: chapterOgPath(course.slug, level.slug, chapter.subject.key, chapter.key),
      imageAlt: `${chapter.name}, ${chapter.subject.name} (${course.name} ${level.name})`,
      type: 'article',
      jsonLd: [
        breadcrumbJsonLd([
          { name: 'Home', path: '/' },
          { name: 'Courses', path: '/courses' },
          { name: course.name, path: `/courses/${course.slug}` },
          { name: level.name, path: `/courses/${course.slug}/${level.slug}` },
          { name: chapter.subject.name, path: `/courses/${course.slug}/${level.slug}/${chapter.subject.key}` },
          { name: chapter.name, path },
        ]),
        {
          '@context': 'https://schema.org',
          '@type': 'Article',
          headline: `${chapter.name}: ${chapter.subject.name}`,
          about: `${course.name} ${level.name} ${chapter.subject.name}`,
        },
      ],
    })
  },
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
