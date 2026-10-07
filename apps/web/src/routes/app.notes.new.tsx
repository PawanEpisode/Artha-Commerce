import { createFileRoute } from '@tanstack/react-router'

import { NewNoteContainer, newNoteSchema } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/new')({
  validateSearch: newNoteSchema,
  head: () =>
    buildHead({
      title: 'New note',
      description: 'Write a new note.',
      path: '/app/notes/new',
      noindex: true,
    }),
  component: function NewNoteRoute() {
    return <NewNoteContainer search={Route.useSearch()} />
  },
})
