import { createFileRoute } from '@tanstack/react-router'

import { NewCardContainer, newCardSearchSchema } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/cards/new')({
  validateSearch: newCardSearchSchema,
  head: () =>
    buildHead({
      title: 'Make a card',
      description: 'Make a revision card.',
      path: '/app/recall/cards/new',
      noindex: true,
    }),
  component: function NewCardRoute() {
    return <NewCardContainer search={Route.useSearch()} />
  },
})
