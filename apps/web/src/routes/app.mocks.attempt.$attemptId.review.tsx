import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { AttemptReviewContainer } from '~/modules/mocktest'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mocks/attempt/$attemptId/review')({
  head: () =>
    buildHead({
      title: 'Mock Test Solution Review',
      description: 'Comprehensive review with solutions, choice rules, and answer explanations.',
      path: '/app/mocks',
      noindex: true,
    }),
  component: function MockAttemptReviewRoute() {
    const { attemptId } = Route.useParams()
    const navigate = useNavigate()

    return (
      <AttemptReviewContainer
        attemptId={attemptId}
        onBackToResult={(targetAttemptId) =>
          navigate({
            to: '/app/mocks/attempt/$attemptId/result',
            params: { attemptId: targetAttemptId },
          })
        }
        onBackToMocks={() => navigate({ to: '/app/mocks' })}
      />
    )
  },
})
