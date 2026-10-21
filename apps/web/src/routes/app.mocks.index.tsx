import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { MockCatalogContainer } from '~/modules/mocktest'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mocks/')({
  head: () =>
    buildHead({
      title: 'Mock Tests & MTP Series',
      description: 'Official format timed mock tests with CBT shell, blueprint choice rules, and percentile ranking.',
      path: '/app/mocks',
      noindex: true,
    }),
  component: function MockCatalogRoute() {
    const navigate = useNavigate()
    return (
      <MockCatalogContainer
        onSelectPaper={(paperId) => navigate({ to: '/app/mocks/papers/$paperId', params: { paperId } })}
      />
    )
  },
})
