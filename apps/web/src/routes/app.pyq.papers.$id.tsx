import { createFileRoute } from '@tanstack/react-router'

import { PaperDetailContainer } from '~/modules/pyq'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/pyq/papers/$id')({
  head: () =>
    buildHead({
      title: 'Exam Paper Details & Questions',
      description: 'Past exam paper question breakdown, marks and solutions.',
      path: '/app/pyq',
      noindex: true,
    }),
  component: function PaperDetailRoute() {
    const { id } = Route.useParams()
    return <PaperDetailContainer paperId={id} />
  },
})
