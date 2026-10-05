import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { SubjectContainer } from '~/modules/coverage'
import { buildHead } from '~/modules/seo'

const search = z.object({
  view: z.enum(['weighted', 'simple']).optional().catch(undefined),
})

export const Route = createFileRoute('/app/syllabus/$subject/')({
  validateSearch: search,
  head: () =>
    buildHead({
      title: 'Subject coverage',
      description: 'Your progress in this paper.',
      path: '/app/syllabus',
      noindex: true,
    }),
  component: function SubjectRoute() {
    const { subject } = Route.useParams()
    return <SubjectContainer subjectId={subject} search={Route.useSearch()} />
  },
})
