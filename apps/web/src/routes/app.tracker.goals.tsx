import { createFileRoute } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'
import { GoalsContainer } from '~/modules/tracker'

export const Route = createFileRoute('/app/tracker/goals')({
  head: () =>
    buildHead({
      title: 'Study goals',
      description: 'Daily and weekly study goals.',
      path: '/app/tracker/goals',
      noindex: true,
    }),
  component: GoalsContainer,
})
