import { createFileRoute } from '@tanstack/react-router'

import { ProgressionWizardContainer } from '~/modules/progression'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/transition')({
  head: () =>
    buildHead({
      title: 'Level Transition & Progression',
      description: 'Graduate to the next academic tier, declare group clearance, and record paper exemptions.',
      path: '/app/transition',
      noindex: true,
    }),
  component: ProgressionWizardContainer,
})
