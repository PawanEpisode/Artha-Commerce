import { createFileRoute } from '@tanstack/react-router'

import { BookmarksContainer } from '~/modules/practice'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/practice/bookmarks')({
  head: () =>
    buildHead({
      title: 'Bookmarked Questions',
      description: 'Review your saved and flagged questions.',
      path: '/app/practice/bookmarks',
      noindex: true,
    }),
  component: BookmarksContainer,
})
