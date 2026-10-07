import { createFileRoute } from '@tanstack/react-router'

import { ChapterNotesContainer, noteFilterSchema } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/$subject/$chapter')({
  validateSearch: noteFilterSchema,
  head: () =>
    buildHead({
      title: 'Chapter notes',
      description: 'Every note, highlight and document of one chapter.',
      path: '/app/notes',
      noindex: true,
    }),
  component: function ChapterNotesRoute() {
    const { subject, chapter } = Route.useParams()
    return <ChapterNotesContainer subject={subject} chapter={chapter} search={Route.useSearch()} />
  },
})
