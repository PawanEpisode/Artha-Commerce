import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { PaperDetailContainer } from '~/modules/mocktest'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mocks/papers/$paperId')({
  head: () =>
    buildHead({
      title: 'Mock Test Paper Details',
      description: 'Exam blueprint, instructions, sections, and start exam shell.',
      path: '/app/mocks',
      noindex: true,
    }),
  component: function MockPaperDetailRoute() {
    const { paperId } = Route.useParams()
    const navigate = useNavigate()

    return (
      <PaperDetailContainer
        paperId={paperId}
        onStartAttempt={(attemptId) => navigate({ to: '/app/mocks/attempt/$attemptId', params: { attemptId } })}
        onBack={() => navigate({ to: '/app/mocks' })}
      />
    )
  },
})
