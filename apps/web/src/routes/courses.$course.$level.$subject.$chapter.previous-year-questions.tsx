import { createFileRoute, notFound } from '@tanstack/react-router'

import { findLevel, loadCourse } from '~/modules/courses'
import { publicPage } from '~/modules/layout'
import { getChapterPyqs, PublicPyqChapterContainer } from '~/modules/pyq'
import { buildHead } from '~/modules/seo'
import { fetchChapter } from '~/modules/syllabus'

export const Route = createFileRoute('/courses/$course/$level/$subject/$chapter/previous-year-questions')({
  staticData: publicPage,
  loader: async ({ params }) => {
    const course = await loadCourse(params.course)
    const level = course && findLevel(course, params.level)
    if (!course || !level) throw notFound()
    const chapter = await fetchChapter(params.course, params.level, params.subject, params.chapter)
    if (!chapter) throw notFound()
    const pyqs = await getChapterPyqs(chapter.id).catch(() => [])
    return { course, level, chapter, pyqs }
  },
  head: ({ loaderData }) =>
    buildHead({
      title: loaderData
        ? `${loaderData.chapter.name} Previous Year Questions: ${loaderData.chapter.subject.name}, ${loaderData.course.name} ${loaderData.level.name}`
        : 'Previous Year Questions',
      description: loaderData
        ? `Past paper exam questions and suggested answers for ${loaderData.chapter.name} (${loaderData.course.name} ${loaderData.level.name}).`
        : 'Previous year exam questions and solutions.',
      path: loaderData
        ? `/courses/${loaderData.course.slug}/${loaderData.level.slug}/${loaderData.chapter.subject.key}/${loaderData.chapter.key}/previous-year-questions`
        : '/courses',
    }),
  component: function ChapterPyqRoute() {
    const { course, level, chapter, pyqs } = Route.useLoaderData()
    return (
      <PublicPyqChapterContainer
        courseName={course.name}
        levelName={level.name}
        subjectName={chapter.subject.name}
        chapterName={chapter.name}
        courseSlug={course.slug}
        levelSlug={level.slug}
        subjectSlug={chapter.subject.key}
        chapterSlug={chapter.key}
        items={pyqs}
      />
    )
  },
})
