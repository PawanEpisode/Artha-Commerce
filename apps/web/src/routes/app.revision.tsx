import { createFileRoute } from '@tanstack/react-router'

import { RevisionContainer } from '~/modules/coverage'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/revision')({
  head: () =>
    buildHead({
      title: 'Due for revision',
      description: 'Chapters to revise today.',
      path: '/app/revision',
      noindex: true,
    }),
  component: RevisionContainer,
})
