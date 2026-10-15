import { createFileRoute, notFound } from '@tanstack/react-router'

import { findLevel, loadCourse } from '~/modules/courses'
import { publicPage } from '~/modules/layout'
import { getPublicQuestions, PublicChapterQuestionsContainer } from '~/modules/questionbank'
import { buildHead } from '~/modules/seo'
import { fetchChapter } from '~/modules/syllabus'

export const Route = createFileRoute('/courses/$course/$level/$subject/$chapter/questions')({
  staticData: publicPage,
  loader: async ({ params }) => {
    const course = await loadCourse(params.course)
    const level = course && findLevel(course, params.level)
    if (!course || !level) throw notFound()
    const chapter = await fetchChapter(params.course, params.level, params.subject, params.chapter)
    if (!chapter) throw notFound()
    const qRes = await getPublicQuestions({ chapter: chapter.key, limit: 20 }).catch(() => ({ items: [] }))
    return { course, level, chapter, questions: qRes.items }
  },
  head: ({ loaderData }) =>
    buildHead({
      title: loaderData
        ? `${loaderData.chapter.name} Questions: ${loaderData.chapter.subject.name}, ${loaderData.course.name} ${loaderData.level.name}`
        : 'Chapter Questions',
      description: loaderData
        ? `Practise questions for ${loaderData.chapter.name} in ${loaderData.chapter.subject.name} (${loaderData.course.name} ${loaderData.level.name}).`
        : 'Chapter questions and interactive practice.',
      path: loaderData
        ? `/courses/${loaderData.course.slug}/${loaderData.level.slug}/${loaderData.chapter.subject.key}/${loaderData.chapter.key}/questions`
        : '/courses',
    }),
  component: function ChapterQuestionsRoute() {
    const { course, level, chapter, questions } = Route.useLoaderData()
    return (
      <PublicChapterQuestionsContainer
        courseName={course.name}
        levelName={level.name}
        subjectName={chapter.subject.name}
        chapterName={chapter.name}
        courseSlug={course.slug}
        levelSlug={level.slug}
        subjectSlug={chapter.subject.key}
        chapterSlug={chapter.key}
        questions={questions}
      />
    )
  },
})
