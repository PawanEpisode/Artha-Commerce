import { createFileRoute } from '@tanstack/react-router'

import { mcqFilterSchema, McqSetsContainer } from '~/modules/mcqbank'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mcq/sets/')({
  validateSearch: mcqFilterSchema,
  head: () =>
    buildHead({
      title: 'MCQ Practice Sets: Platform Sprints & ICMAI Booklets',
      description: 'Full catalog of curated MCQ sets, official ICMAI booklets, and exam practice papers.',
      path: '/app/mcq/sets',
      noindex: true,
    }),
  component: function McqSetsRoute() {
    const search = Route.useSearch()
    return <McqSetsContainer initialFilter={search} />
  },
})
