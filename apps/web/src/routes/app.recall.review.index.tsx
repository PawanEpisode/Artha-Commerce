import { createFileRoute } from '@tanstack/react-router'

import { ReviewContainer, reviewSearchSchema } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/review/')({
  validateSearch: reviewSearchSchema,
  head: () =>
    buildHead({
      title: 'Review',
      description: 'Review your cards.',
      path: '/app/recall/review',
      noindex: true,
    }),
  component: function ReviewRoute() {
    return <ReviewContainer search={Route.useSearch()} />
  },
})
