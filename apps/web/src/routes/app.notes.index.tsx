import { createFileRoute } from '@tanstack/react-router'

import { NotesHubContainer } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/')({
  head: () =>
    buildHead({
      title: 'Notes',
      description: 'Your notes, by subject and chapter.',
      path: '/app/notes',
      noindex: true,
    }),
  component: NotesHubContainer,
})
