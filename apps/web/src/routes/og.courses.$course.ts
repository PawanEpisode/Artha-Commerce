import { createFileRoute } from '@tanstack/react-router'

import { env } from '~/lib/env'
import { loadCourse } from '~/modules/courses'
import { courseCard, DEFAULT_OG_IMAGE, ogResponse } from '~/modules/seo'
// Deliberately not in the seo barrel: it loads native code that must only ever reach the server bundle.
import { renderOgPng } from '~/modules/seo/og-render'

/** Preview image of a course page (and of its level and paper pages). Falls back to the site image on any failure. */
export const Route = createFileRoute('/og/courses/$course')({
  server: {
    handlers: {
      GET: async ({ params }) => {
        try {
          const course = await loadCourse(params.course)
          if (!course) return ogResponse.notFound()
          const card = courseCard({
            name: course.name,
            fullName: course.fullName,
            body: course.body,
            levels: course.levels.map((l) => l.name),
            description: course.description,
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
