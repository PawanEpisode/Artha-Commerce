import { createFileRoute } from '@tanstack/react-router'

import { DeckDetailContainer } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/decks/$deckId')({
  head: ({ params }) =>
    buildHead({
      title: 'Deck',
      description: 'A ready-made revision deck.',
      path: `/app/recall/decks/${params.deckId}`,
      noindex: true,
    }),
  component: function DeckDetailRoute() {
    return <DeckDetailContainer deckId={Route.useParams().deckId} />
  },
})
