import { createFileRoute } from '@tanstack/react-router'

import { LibraryContainer, librarySearchSchema } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/library')({
  validateSearch: librarySearchSchema,
  head: () =>
    buildHead({
      title: 'PDF library',
      description: 'Your PDFs, ready to read and mark.',
      path: '/app/notes/library',
      noindex: true,
    }),
  component: function LibraryRoute() {
    return <LibraryContainer search={Route.useSearch()} />
  },
})
