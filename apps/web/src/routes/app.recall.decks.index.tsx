import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { DecksContainer, decksSearchSchema } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/decks/')({
  validateSearch: decksSearchSchema,
  head: () =>
    buildHead({
      title: 'Decks',
      description: 'Ready-made revision cards.',
      path: '/app/recall/decks',
      noindex: true,
    }),
  component: function DecksRoute() {
    const navigate = useNavigate()
    return (
      <DecksContainer
        search={Route.useSearch()}
        onSearch={(next) => void navigate({ to: '/app/recall/decks', search: next, replace: true })}
      />
    )
  },
})
