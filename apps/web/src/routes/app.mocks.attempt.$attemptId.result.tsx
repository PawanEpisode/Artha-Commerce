import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { AttemptResultContainer } from '~/modules/mocktest'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mocks/attempt/$attemptId/result')({
  head: () =>
    buildHead({
      title: 'Mock Test Results & Scorecard',
      description: 'Exam score, percentile rank, section breakdown, and choice rule report.',
      path: '/app/mocks',
      noindex: true,
    }),
  component: function MockAttemptResultRoute() {
    const { attemptId } = Route.useParams()
    const navigate = useNavigate()

    return (
      <AttemptResultContainer
        attemptId={attemptId}
        onReview={(targetAttemptId) =>
          navigate({
            to: '/app/mocks/attempt/$attemptId/review',
            params: { attemptId: targetAttemptId },
          })
        }
        onBackToMocks={() => navigate({ to: '/app/mocks' })}
      />
    )
  },
})
