import { createFileRoute } from '@tanstack/react-router'

import { EditorReviewQueueContainer } from '~/modules/questionbank'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/questions/editor')({
  head: () =>
    buildHead({
      title: 'Editorial Review Queue & Quality',
      description: 'Review submissions, triage reports and import question batches.',
      path: '/app/questions/editor',
      noindex: true,
    }),
  component: function QuestionEditorRoute() {
    return <EditorReviewQueueContainer />
  },
})
