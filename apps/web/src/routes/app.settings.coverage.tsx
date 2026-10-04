import { createFileRoute } from '@tanstack/react-router'

import { CoverageSettingsContainer } from '~/modules/coverage'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/settings/coverage')({
  head: () =>
    buildHead({
      title: 'Coverage settings',
      description: 'Weights and revision schedule.',
      path: '/app/settings/coverage',
      noindex: true,
    }),
  component: CoverageSettingsContainer,
})
