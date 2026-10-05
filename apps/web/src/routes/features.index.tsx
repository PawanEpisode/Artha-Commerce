import { createFileRoute } from '@tanstack/react-router'

import { FeaturesIndexContainer } from '~/modules/features'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/features/')({
  head: () =>
    buildHead({
      title: 'Features',
      description:
        'Syllabus tracking, a Pomodoro focus timer and a study time tracker are ready for CA, CS and CMA students. Mocks, notes and more are coming soon.',
      path: '/features',
    }),
  component: FeaturesIndexContainer,
})
