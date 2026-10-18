import { createFileRoute } from '@tanstack/react-router'

import { McqChapterDetailContainer } from '~/modules/mcqbank'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mcq/subjects/$subject/chapters/$chapter')({
  head: ({ params }) =>
    buildHead({
      title: `MCQs: ${params.chapter}`,
      description: 'Browse and practise the multiple choice questions of one chapter.',
      path: `/app/mcq/subjects/${params.subject}/chapters/${params.chapter}`,
      noindex: true,
    }),
  component: function McqChapterRoute() {
    const { subject, chapter } = Route.useParams()
    return <McqChapterDetailContainer subjectKey={subject} chapterKey={chapter} />
  },
})
