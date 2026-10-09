import { createFileRoute } from '@tanstack/react-router'

import { StatsContainer, statsSearchSchema } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/stats')({
  validateSearch: statsSearchSchema,
  head: () =>
    buildHead({
      title: 'Revision stats',
      description: 'How much you reviewed and remember.',
      path: '/app/recall/stats',
      noindex: true,
    }),
  component: function StatsRoute() {
    return <StatsContainer search={Route.useSearch()} />
  },
})
