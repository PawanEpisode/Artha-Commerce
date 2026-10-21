import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { ExamShellContainer } from '~/modules/mocktest'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mocks/attempt/$attemptId')({
  head: () =>
    buildHead({
      title: 'Exam CBT Shell',
      description: 'Official CBT exam interface with real-time timer and autosave.',
      path: '/app/mocks',
      noindex: true,
    }),
  component: function MockExamShellRoute() {
    const { attemptId } = Route.useParams()
    const navigate = useNavigate()

    return (
      <ExamShellContainer
        attemptId={attemptId}
        onFinish={(finishedAttemptId) =>
          navigate({
            to: '/app/mocks/attempt/$attemptId/result',
            params: { attemptId: finishedAttemptId },
          })
        }
        onExit={() => navigate({ to: '/app/mocks' })}
      />
    )
  },
})
