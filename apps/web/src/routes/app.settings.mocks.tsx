import { createFileRoute } from '@tanstack/react-router'

import { MockSettingsContainer } from '~/modules/mocktest'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/settings/mocks')({
  head: () =>
    buildHead({
      title: 'Mock Tests & Exam Settings',
      description: 'Extra time accommodation, CBT keyboard shortcuts, and default practice mode.',
      path: '/app/settings/mocks',
      noindex: true,
    }),
  component: MockSettingsContainer,
})
