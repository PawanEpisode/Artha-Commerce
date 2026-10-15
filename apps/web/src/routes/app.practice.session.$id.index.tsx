import { createFileRoute } from '@tanstack/react-router'

import { PracticePlayerContainer, practicePlayerSearchSchema } from '~/modules/practice'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/practice/session/$id/')({
  validateSearch: practicePlayerSearchSchema,
  head: () =>
    buildHead({
      title: 'Practice Session',
      description: 'Interactive question runner and test player.',
      path: '/app/practice/session',
      noindex: true,
    }),
  component: function PracticePlayerRoute() {
    const { id } = Route.useParams()
    const { q } = Route.useSearch()
    return <PracticePlayerContainer sessionId={id} initialPosition={q} />
  },
})
