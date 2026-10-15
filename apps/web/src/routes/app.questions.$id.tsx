import { createFileRoute } from '@tanstack/react-router'

import { QuestionDetailContainer } from '~/modules/questionbank'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/questions/$id')({
  head: () =>
    buildHead({
      title: 'Question Detail',
      description: 'View full question stem, options, explanation and references.',
      path: '/app/questions',
      noindex: true,
    }),
  component: function QuestionDetailRoute() {
    const { id } = Route.useParams()
    return <QuestionDetailContainer questionId={id} />
  },
})
