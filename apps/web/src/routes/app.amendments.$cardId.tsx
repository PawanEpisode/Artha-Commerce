import { createFileRoute } from '@tanstack/react-router'

import { MyCardDetailContainer } from '~/modules/amendments'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/amendments/$cardId')({
  head: () =>
    buildHead({
      title: 'Amendment Detail',
      description: 'Statutory amendment diff, impact, and official authority source.',
      path: '/app/amendments',
      noindex: true,
    }),
  component: function CardDetailRoute() {
    const { cardId } = Route.useParams()
    return <MyCardDetailContainer cardId={cardId} />
  },
})
