import { createFileRoute } from '@tanstack/react-router'

import { MistakesContainer } from '~/modules/practice'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/practice/mistakes')({
  head: () =>
    buildHead({
      title: 'My Mistakes',
      description: 'Review and retry questions you previously answered incorrectly.',
      path: '/app/practice/mistakes',
      noindex: true,
    }),
  component: MistakesContainer,
})
