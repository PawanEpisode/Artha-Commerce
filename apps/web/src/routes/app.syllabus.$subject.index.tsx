import { createFileRoute } from '@tanstack/react-router'

import { SubjectContainer } from '~/modules/coverage'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/syllabus/$subject/')({
  head: () =>
    buildHead({
      title: 'Subject coverage',
      description: 'Your progress in this paper.',
      path: '/app/syllabus',
      noindex: true,
    }),
  component: function SubjectRoute() {
    const { subject } = Route.useParams()
    return <SubjectContainer subjectId={subject} />
  },
})
