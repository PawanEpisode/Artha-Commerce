import { createFileRoute } from '@tanstack/react-router'

import { ChapterContainer } from '~/modules/coverage'
import { buildHead } from '~/modules/seo'
import { useAutoCapture } from '~/modules/tracker'

export const Route = createFileRoute('/app/syllabus/$subject/$chapter')({
  head: () =>
    buildHead({
      title: 'Chapter coverage',
      description: 'Your progress in this chapter.',
      path: '/app/syllabus',
      noindex: true,
    }),
  component: function ChapterRoute() {
    const { subject, chapter } = Route.useParams()
    useAutoCapture(chapter)
    return <ChapterContainer subjectId={subject} chapterId={chapter} />
  },
})
