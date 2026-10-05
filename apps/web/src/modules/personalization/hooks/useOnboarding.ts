import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { track } from '~/modules/observability'

import { completeOnboarding, getOnboarding, putStep, skipStep } from '../lib/api'
import { personalizationKeys } from '../lib/keys'
import type { OnboardingState } from '../lib/types'
import { useBootstrap } from './useBootstrap'

/** The step list and status (`GET /me/onboarding/`). Always fresh when the flow opens. */
export function useOnboardingState() {
  const { signedIn } = useBootstrap()
  return useQuery({
    queryKey: personalizationKeys.onboarding,
    queryFn: getOnboarding,
    enabled: signedIn,
    staleTime: 0,
    retry: 1,
  })
}

/** Saves one step through the owning module and keeps the cached state in step with the server's answer. */
export function useSaveStep(key: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => putStep(key, body),
    onSuccess: (state: OnboardingState) => {
      qc.setQueryData(personalizationKeys.onboarding, state)
      track('onboarding_step_completed', { step: key })
    },
  })
}

export function useSkipStep(key: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => skipStep(key),
    onSuccess: (state: OnboardingState) => {
      qc.setQueryData(personalizationKeys.onboarding, state)
      track('onboarding_step_skipped', { step: key })
    },
  })
}

/**
 * Finishes onboarding. The bootstrap is refetched BEFORE the mutation resolves, so the gate already sees "completed"
 * when the student is sent on, and the celebration can use the fresh course summary.
 */
export function useCompleteOnboarding() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: completeOnboarding,
    onSuccess: async (completion) => {
      qc.setQueryData(personalizationKeys.onboarding, completion.state)
      await qc.invalidateQueries({ queryKey: personalizationKeys.bootstrap })
      // Coverage screens read the new enrolment, targets and daily time.
      await qc.invalidateQueries({ queryKey: ['coverage'] })
    },
  })
}
