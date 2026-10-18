import { createFileRoute } from '@tanstack/react-router'

import { McqSubjectContainer } from '~/modules/mcqbank'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mcq/subjects/$subject/')({
  head: ({ params }) =>
    buildHead({
      title: `MCQs: ${params.subject}`,
      description: `Browse chapters and practice multiple choice questions for ${params.subject}.`,
      path: `/app/mcq/subjects/${params.subject}`,
      noindex: true,
    }),
  component: function McqSubjectRoute() {
    const { subject } = Route.useParams()
    return <McqSubjectContainer subjectKey={subject} />
  },
})
