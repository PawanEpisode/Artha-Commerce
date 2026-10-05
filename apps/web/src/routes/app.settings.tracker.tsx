import { createFileRoute } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'
import { TrackerSettingsContainer } from '~/modules/tracker'

export const Route = createFileRoute('/app/settings/tracker')({
  head: () =>
    buildHead({
      title: 'Tracker settings',
      description: 'Idle check, week start and time zone.',
      path: '/app/settings/tracker',
      noindex: true,
    }),
  component: TrackerSettingsContainer,
})
