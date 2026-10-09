import { createFileRoute } from '@tanstack/react-router'

import { HubContainer } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/')({
  head: () =>
    buildHead({
      title: 'Revision',
      description: 'Your cards due today.',
      path: '/app/recall',
      noindex: true,
    }),
  component: HubContainer,
})
