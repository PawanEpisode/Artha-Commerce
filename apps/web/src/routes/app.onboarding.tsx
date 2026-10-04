import { createFileRoute } from '@tanstack/react-router'

import { OnboardingContainer } from '~/modules/coverage'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/onboarding')({
  head: () =>
    buildHead({
      title: 'Set up My Coverage',
      description: 'Choose your course and level.',
      path: '/app/onboarding',
      noindex: true,
    }),
  component: OnboardingContainer,
})
