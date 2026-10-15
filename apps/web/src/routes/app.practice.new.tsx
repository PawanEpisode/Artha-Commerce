import { createFileRoute } from '@tanstack/react-router'

import { PracticeBuilderContainer, practiceBuilderSearchSchema } from '~/modules/practice'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/practice/new')({
  validateSearch: practiceBuilderSearchSchema,
  head: () =>
    buildHead({
      title: 'Build Practice Test',
      description: 'Configure and start a custom test or chapter quiz.',
      path: '/app/practice/new',
      noindex: true,
    }),
  component: function PracticeBuilderRoute() {
    return <PracticeBuilderContainer initialSearch={Route.useSearch()} />
  },
})
