import { createFileRoute } from '@tanstack/react-router'

import { PracticeReviewContainer } from '~/modules/practice'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/practice/session/$id/review')({
  head: () =>
    buildHead({
      title: 'Practice Review',
      description: 'Review your results, answers, and detailed explanations.',
      path: '/app/practice/session/review',
      noindex: true,
    }),
  component: function PracticeReviewRoute() {
    const { id } = Route.useParams()
    return <PracticeReviewContainer sessionId={id} />
  },
})
