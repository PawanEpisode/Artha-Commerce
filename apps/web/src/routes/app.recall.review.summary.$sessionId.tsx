import { createFileRoute } from '@tanstack/react-router'

import { SummaryContainer } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/review/summary/$sessionId')({
  head: () =>
    buildHead({
      title: 'Session summary',
      description: 'How your review session went.',
      path: '/app/recall/review/summary',
      noindex: true,
    }),
  component: function SummaryRoute() {
    return <SummaryContainer sessionId={Route.useParams().sessionId} />
  },
})
