import { createFileRoute } from '@tanstack/react-router'

import { PublicShareContainer } from '~/modules/analytics'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/analytics/share/$token')({
  head: () =>
    buildHead({
      title: 'Shared Progress Report',
      description: 'Verified student exam readiness and practice analytics report.',
      path: '/app/analytics/share',
      noindex: true,
    }),
  component: function PublicShareRoute() {
    const { token } = Route.useParams()
    return <PublicShareContainer token={token} />
  },
})
