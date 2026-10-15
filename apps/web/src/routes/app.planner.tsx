import { createFileRoute } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'
import { PlannerContainer } from '~/modules/today'

export const Route = createFileRoute('/app/planner')({
  head: () =>
    buildHead({
      title: 'Study plan',
      description: 'Dates for reading, revision and mocks, worked out from your exam date.',
      path: '/app/planner',
      noindex: true,
    }),
  component: PlannerContainer,
})
