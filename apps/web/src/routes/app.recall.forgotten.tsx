import { createFileRoute } from '@tanstack/react-router'

import { ForgottenContainer } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/forgotten')({
  head: () =>
    buildHead({
      title: 'Slipping away',
      description: 'Cards you keep missing.',
      path: '/app/recall/forgotten',
      noindex: true,
    }),
  component: ForgottenContainer,
})
