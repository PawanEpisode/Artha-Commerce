import { createFileRoute } from '@tanstack/react-router'

import { PracticeHubContainer } from '~/modules/practice'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/practice/')({
  head: () =>
    buildHead({
      title: 'Practice Hub',
      description: 'Interactive question practice, chapter drills, and past papers.',
      path: '/app/practice',
      noindex: true,
    }),
  component: PracticeHubContainer,
})
