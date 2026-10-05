import { createFileRoute } from '@tanstack/react-router'

import { SettingsContainer } from '~/modules/focus'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/settings/focus')({
  head: () =>
    buildHead({
      title: 'Focus settings',
      description: 'Presets, breaks and alerts for the focus timer.',
      path: '/app/settings/focus',
      noindex: true,
    }),
  component: SettingsContainer,
})
