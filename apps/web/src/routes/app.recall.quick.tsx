import { createFileRoute } from '@tanstack/react-router'

import { QuickContainer, quickSearchSchema } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/quick')({
  validateSearch: quickSearchSchema,
  head: () =>
    buildHead({
      title: 'Quick revision',
      description: 'Refresh what could fade before your exam.',
      path: '/app/recall/quick',
      noindex: true,
    }),
  component: function QuickRoute() {
    return <QuickContainer search={Route.useSearch()} />
  },
})
