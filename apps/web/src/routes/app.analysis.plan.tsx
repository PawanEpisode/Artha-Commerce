import { createFileRoute } from '@tanstack/react-router'

import { PlannerContainer } from '~/modules/paperanalysis'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/analysis/plan')({
  head: () =>
    buildHead({
      title: 'N-Days Revision Planner',
      description: 'Generate high-yield revision plans based on historical exam chapter yields.',
      path: '/app/analysis/plan',
      noindex: true,
    }),
  component: PlannerContainer,
})
