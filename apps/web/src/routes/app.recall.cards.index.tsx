import { createFileRoute } from '@tanstack/react-router'

import { CardsContainer, cardsSearchSchema } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/cards/')({
  validateSearch: cardsSearchSchema,
  head: () =>
    buildHead({
      title: 'Your cards',
      description: 'Find, fix and organise your revision cards.',
      path: '/app/recall/cards',
      noindex: true,
    }),
  component: function CardsRoute() {
    return <CardsContainer search={Route.useSearch()} />
  },
})
