import { createFileRoute } from '@tanstack/react-router'

import { NoteEditorContainer, noteEditorSchema } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/n/$noteId')({
  validateSearch: noteEditorSchema,
  head: () =>
    buildHead({
      title: 'Note',
      description: 'Read and edit a note.',
      path: '/app/notes',
      noindex: true,
    }),
  component: function NoteRoute() {
    return <NoteEditorContainer noteId={Route.useParams().noteId} search={Route.useSearch()} />
  },
})
