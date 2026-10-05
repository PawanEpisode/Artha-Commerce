import { createFileRoute } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'
import { LogContainer } from '~/modules/tracker'

export const Route = createFileRoute('/app/tracker/log')({
  head: () =>
    buildHead({
      title: 'Session log',
      description: 'Every study session you logged.',
      path: '/app/tracker/log',
      noindex: true,
    }),
  component: LogContainer,
})
