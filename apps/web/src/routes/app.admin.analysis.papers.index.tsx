import { createFileRoute } from '@tanstack/react-router'

import { PapersBoardContainer } from '~/modules/paperanalysis'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/admin/analysis/papers/')({
  head: () =>
    buildHead({
      title: 'Editorial Papers Workbench',
      description: 'Create and verify past exam sittings and chapter allocations.',
      path: '/app/admin/analysis/papers',
      noindex: true,
    }),
  component: PapersBoardContainer,
})
