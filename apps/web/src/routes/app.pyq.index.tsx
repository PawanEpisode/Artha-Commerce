import { createFileRoute } from '@tanstack/react-router'

import { PyqHomeContainer, pyqSearchSchema } from '~/modules/pyq'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/pyq/')({
  validateSearch: pyqSearchSchema,
  head: () =>
    buildHead({
      title: 'Previous Year Questions & Past Papers',
      description:
        'CMA Intermediate and Final past exam question papers, suggested solutions and interactive practice.',
      path: '/app/pyq',
      noindex: true,
    }),
  component: function PyqHomeRoute() {
    return <PyqHomeContainer search={Route.useSearch()} />
  },
})
