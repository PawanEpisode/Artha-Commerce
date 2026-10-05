import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { z } from 'zod'

import { safeNextPath } from '~/modules/auth'
import { OnboardingContainer as LegacyOnboardingContainer } from '~/modules/coverage'
import { useFeatureFlag } from '~/modules/observability'
import { OnboardingContainer } from '~/modules/personalization'
import { buildHead } from '~/modules/seo'

const optionalText = z.string().min(1).optional().catch(undefined)

export const Route = createFileRoute('/app/onboarding')({
  validateSearch: z.object({
    step: optionalText,
    next: optionalText,
    course: optionalText,
    level: optionalText,
  }),
  head: () =>
    buildHead({
      title: 'Set up your workspace',
      description: 'A few quick questions so the workspace fits your exam.',
      path: '/app/onboarding',
      noindex: true,
    }),
  component: function OnboardingRoute() {
    const search = Route.useSearch()
    const navigate = useNavigate()
    const personalization = useFeatureFlag('personalization')

    // Flag off: the original two-step coverage setup keeps working untouched.
    if (!personalization) return <LegacyOnboardingContainer initialCourse={search.course} initialLevel={search.level} />

    return (
      <OnboardingContainer
        search={search}
        destination={safeNextPath(search.next)}
        onStep={(step, options) =>
          void navigate({ to: '/app/onboarding', search: (prev) => ({ ...prev, step }), replace: options?.replace })
        }
      />
    )
  },
})
