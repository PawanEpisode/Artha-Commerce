import { createFileRoute } from '@tanstack/react-router'

import { NotesSettingsContainer } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/settings/notes')({
  head: () =>
    buildHead({
      title: 'Notes settings',
      description: 'Storage, export and deleting your notes.',
      path: '/app/settings/notes',
      noindex: true,
    }),
  component: NotesSettingsContainer,
})
