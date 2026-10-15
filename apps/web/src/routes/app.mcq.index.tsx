import { createFileRoute } from '@tanstack/react-router'

import { McqHomeContainer } from '~/modules/mcqbank'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mcq/')({
  head: () =>
    buildHead({
      title: 'MCQ Bank: CMA Intermediate & Final',
      description:
        'Targeted multiple choice practice, ICMAI MCQ booklets, and custom chapter sprints for CMA Syllabus 2022.',
      path: '/app/mcq',
      noindex: true,
    }),
  component: function McqHomeRoute() {
    return <McqHomeContainer />
  },
})
