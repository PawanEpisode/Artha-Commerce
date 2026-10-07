import { createFileRoute } from '@tanstack/react-router'

import { noteFilterSchema, SubjectNotesContainer } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/$subject/')({
  validateSearch: noteFilterSchema,
  head: () =>
    buildHead({
      title: 'Subject notes',
      description: 'Every note, highlight and document of one subject.',
      path: '/app/notes',
      noindex: true,
    }),
  component: function SubjectNotesRoute() {
    return <SubjectNotesContainer subject={Route.useParams().subject} search={Route.useSearch()} />
  },
})
