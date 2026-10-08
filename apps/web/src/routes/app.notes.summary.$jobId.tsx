import { createFileRoute } from '@tanstack/react-router'

import { SummaryContainer } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/summary/$jobId')({
  head: () =>
    buildHead({
      title: 'Exam summary',
      description: 'Check an AI exam summary before you save it.',
      path: '/app/notes',
      noindex: true,
    }),
  component: function SummaryRoute() {
    return <SummaryContainer jobId={Route.useParams().jobId} />
  },
})
