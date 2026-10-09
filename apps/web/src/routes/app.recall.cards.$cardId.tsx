import { createFileRoute } from '@tanstack/react-router'

import { CardDetailContainer } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/cards/$cardId')({
  head: ({ params }) =>
    buildHead({
      title: 'Card',
      description: 'See and edit a revision card.',
      path: `/app/recall/cards/${params.cardId}`,
      noindex: true,
    }),
  component: function CardDetailRoute() {
    return <CardDetailContainer cardId={Route.useParams().cardId} />
  },
})
