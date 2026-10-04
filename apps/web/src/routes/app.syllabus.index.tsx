import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { SyllabusMapContainer } from '~/modules/coverage'
import { buildHead } from '~/modules/seo'

const search = z.object({
  view: z.enum(['weighted', 'simple']).optional().catch(undefined),
  status: z.enum(['due']).optional().catch(undefined),
})

export const Route = createFileRoute('/app/syllabus/')({
  validateSearch: search,
  head: () =>
    buildHead({
      title: 'My syllabus coverage',
      description: 'Your progress across every paper.',
      path: '/app/syllabus',
      noindex: true,
    }),
  component: function SyllabusRoute() {
    return <SyllabusMapContainer search={Route.useSearch()} />
  },
})
