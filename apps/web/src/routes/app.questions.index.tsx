import { createFileRoute } from '@tanstack/react-router'

import { QuestionBrowserContainer, questionsSearchSchema } from '~/modules/questionbank'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/questions/')({
  validateSearch: questionsSearchSchema,
  head: () =>
    buildHead({
      title: 'Question Bank',
      description: 'Search, filter and practise past paper and syllabus questions.',
      path: '/app/questions',
      noindex: true,
    }),
  component: function QuestionBrowserRoute() {
    return <QuestionBrowserContainer search={Route.useSearch()} />
  },
})
