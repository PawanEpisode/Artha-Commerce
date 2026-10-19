import { createFileRoute } from '@tanstack/react-router'

import { ProgressionSettingsContainer } from '~/modules/progression'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/settings/progression')({
  head: () =>
    buildHead({
      title: 'Progression settings',
      description: 'Academic tier status, paper exemptions, and transition history.',
      path: '/app/settings/progression',
      noindex: true,
    }),
  component: ProgressionSettingsContainer,
})
