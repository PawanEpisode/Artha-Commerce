import { createFileRoute } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'
import { TrackerContainer } from '~/modules/tracker'

export const Route = createFileRoute('/app/tracker/')({
  head: () =>
    buildHead({
      title: 'Time tracker',
      description: 'Stopwatch, goals and study time today.',
      path: '/app/tracker',
      noindex: true,
    }),
  component: TrackerContainer,
})
