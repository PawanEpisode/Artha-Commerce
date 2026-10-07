import { createFileRoute } from '@tanstack/react-router'

import { NotesTrashContainer } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/trash')({
  head: () =>
    buildHead({
      title: 'Notes trash',
      description: 'Notes you moved to the trash.',
      path: '/app/notes/trash',
      noindex: true,
    }),
  component: NotesTrashContainer,
})
