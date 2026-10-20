import { createFileRoute } from '@tanstack/react-router'

import { ArchiveContainer } from '~/modules/amendments'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/amendments/archive')({
  head: () =>
    buildHead({
      title: 'Amendments Term Archive',
      description: 'Browse past statutory and academic amendment packages by examination attempt.',
      path: '/app/amendments/archive',
      noindex: true,
    }),
  component: ArchiveContainer,
})
