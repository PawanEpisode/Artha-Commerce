import { createFileRoute } from '@tanstack/react-router'

import { env } from '~/lib/env'
import { loadCourse } from '~/modules/courses'
import { chapterCard, DEFAULT_OG_IMAGE, marksLabel, ogResponse } from '~/modules/seo'
// Deliberately not in the seo barrel: it loads native code that must only ever reach the server bundle.
import { renderOgPng } from '~/modules/seo/og-render'
import { fetchChapter } from '~/modules/syllabus'

/** Preview image of a chapter page. Falls back to the site image on any failure. */
export const Route = createFileRoute('/og/courses/$course/$level/$subject/$chapter')({
  server: {
    handlers: {
      GET: async ({ params }) => {
        try {
          const [chapter, course] = await Promise.all([
            fetchChapter(params.course, params.level, params.subject, params.chapter),
            loadCourse(params.course),
          ])
          if (!chapter || !course) return ogResponse.notFound()
          const level = course.levels.find((l) => l.slug === params.level)
          const card = chapterCard({
            courseName: course.name,
            levelName: level?.name ?? params.level,
            subjectName: chapter.subject.name,
            chapterName: chapter.name,
            topicCount: chapter.topics.length,
            marks: marksLabel(chapter.marks_min, chapter.marks_max),
          })
          return ogResponse.png(await renderOgPng(card, env.VITE_SITE_NAME))
        } catch (error) {
          console.error('og image failed', error)
          return ogResponse.fallback(DEFAULT_OG_IMAGE)
        }
      },
    },
  },
})
