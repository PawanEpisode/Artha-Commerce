import { createFileRoute } from '@tanstack/react-router'

import { SuggestionsContainer, suggestionsSearchSchema } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/suggestions')({
  validateSearch: suggestionsSearchSchema,
  head: () =>
    buildHead({
      title: 'Suggest cards with AI',
      description: 'Draft revision cards from your own material.',
      path: '/app/recall/suggestions',
      noindex: true,
    }),
  component: function SuggestionsRoute() {
    return <SuggestionsContainer search={Route.useSearch()} />
  },
})
