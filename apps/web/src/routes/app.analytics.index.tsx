import { createFileRoute } from '@tanstack/react-router'

import { AnalyticsDashboard } from '~/modules/analytics'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/analytics/')({
  head: () =>
    buildHead({
      title: 'Performance Analytics',
      description: 'Exam readiness score, empirical Bayes mastery, and weak topic drills.',
      path: '/app/analytics',
      noindex: true,
    }),
  component: AnalyticsDashboard,
})
