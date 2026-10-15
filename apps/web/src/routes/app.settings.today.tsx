import { createFileRoute } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'
import { TodaySettingsContainer } from '~/modules/today'

export const Route = createFileRoute('/app/settings/today')({
  head: () =>
    buildHead({
      title: 'Today settings',
      description: 'Minutes per day, focus papers and what Today shows.',
      path: '/app/settings/today',
      noindex: true,
    }),
  component: TodaySettingsContainer,
})
