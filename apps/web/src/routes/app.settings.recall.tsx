import { createFileRoute } from '@tanstack/react-router'

import { SettingsContainer } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/settings/recall')({
  head: () =>
    buildHead({
      title: 'Revision settings',
      description: 'Daily limits, target memory and vacation.',
      path: '/app/settings/recall',
      noindex: true,
    }),
  component: SettingsContainer,
})
