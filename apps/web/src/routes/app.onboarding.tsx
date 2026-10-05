import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { OnboardingContainer } from '~/modules/coverage'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/onboarding')({
  validateSearch: z.object({
    course: z.string().min(1).optional().catch(undefined),
    level: z.string().min(1).optional().catch(undefined),
  }),
  head: () =>
    buildHead({
      title: 'Set up My Coverage',
      description: 'Choose your course and level.',
      path: '/app/onboarding',
      noindex: true,
    }),
  component: function OnboardingRoute() {
    const { course, level } = Route.useSearch()
    return <OnboardingContainer initialCourse={course} initialLevel={level} />
  },
})
