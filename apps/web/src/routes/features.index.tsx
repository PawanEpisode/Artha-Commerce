import { createFileRoute } from '@tanstack/react-router'

import { FeaturesIndex } from '~/modules/features'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/features/')({
  head: () =>
    buildHead({
      title: 'Features',
      description:
        'Study planner, syllabus tracker, mock tests, AI doubt solver, notes and flashcards for CA, CS and CMA students.',
      path: '/features',
    }),
  component: FeaturesIndex,
})
