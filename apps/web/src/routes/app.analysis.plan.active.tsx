import { createFileRoute } from '@tanstack/react-router'

import { ActivePlanContainer } from '~/modules/paperanalysis'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/analysis/plan/active')({
  head: () =>
    buildHead({
      title: 'Active Revision Schedule',
      description: 'Your daily revision tasks, replanning controls, and progress.',
      path: '/app/analysis/plan/active',
      noindex: true,
    }),
  component: ActivePlanContainer,
})
