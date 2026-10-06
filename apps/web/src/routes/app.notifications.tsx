import { createFileRoute } from '@tanstack/react-router'

import { InboxContainer } from '~/modules/notifications'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notifications')({
  head: () =>
    buildHead({
      title: 'Inbox',
      description: 'Your recent Artha notifications.',
      path: '/app/notifications',
      noindex: true,
    }),
  component: InboxContainer,
})
