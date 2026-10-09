import { createFileRoute } from '@tanstack/react-router'

import { DecksContainer } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/decks/')({
  head: () =>
    buildHead({
      title: 'Decks',
      description: 'Ready-made revision cards.',
      path: '/app/recall/decks',
      noindex: true,
    }),
  component: DecksContainer,
})
