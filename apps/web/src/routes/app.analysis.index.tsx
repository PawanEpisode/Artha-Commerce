import { createFileRoute } from '@tanstack/react-router'

import { AnalysisHubContainer } from '~/modules/paperanalysis'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/analysis/')({
  head: () =>
    buildHead({
      title: 'Paper Analysis & Recommendations',
      description: 'Historical exam marks analysis, high-yield chapter priority, and N-days study planner.',
      path: '/app/analysis',
      noindex: true,
    }),
  component: AnalysisHubContainer,
})
