import { createFileRoute } from '@tanstack/react-router'

import { NotificationSettingsContainer } from '~/modules/notifications'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/settings/notifications')({
  head: () =>
    buildHead({
      title: 'Notification settings',
      description: 'Choose which alerts Artha sends, when, and to which devices.',
      path: '/app/settings/notifications',
      noindex: true,
    }),
  component: NotificationSettingsContainer,
})
