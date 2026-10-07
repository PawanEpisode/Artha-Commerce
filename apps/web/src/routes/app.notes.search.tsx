import { createFileRoute } from '@tanstack/react-router'

import { noteSearchSchema, NotesSearchContainer } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/search')({
  validateSearch: noteSearchSchema,
  head: () =>
    buildHead({
      title: 'Search notes',
      description: 'Find a note by its words.',
      path: '/app/notes/search',
      noindex: true,
    }),
  component: function NotesSearchRoute() {
    return <NotesSearchContainer search={Route.useSearch()} />
  },
})
