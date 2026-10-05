import { Alert, Celebration, StepFlow } from '@artha/design-system'
import { useRouter } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { useAuth } from '~/modules/auth'
import { track } from '~/modules/observability'

import { LoadErrorPanel, PageColumn, WorkspaceSkeleton } from '../components/LoadStates'
import { AvatarStep } from '../components/steps/AvatarStep'
import { CatchupStep } from '../components/steps/CatchupStep'
import { CourseStep } from '../components/steps/CourseStep'
import { HoursStep } from '../components/steps/HoursStep'
import { ProfileStep } from '../components/steps/ProfileStep'
import { TargetsStep } from '../components/steps/TargetsStep'
import type { StepProps } from '../components/steps/types'
import { useBootstrap } from '../hooks/useBootstrap'
import { useCompleteOnboarding, useOnboardingState } from '../hooks/useOnboarding'
import { useSlow } from '../hooks/useSlow'
import { celebrationMessage, celebrationSeen, markCelebrated } from '../lib/celebration'
import { copyFor, nextAfter, previousBefore, resolveStep, walkOf } from '../lib/onboardingSteps'
import { describeStepError } from '../lib/stepErrors'

export interface OnboardingSearch {
  step?: string
  /** A deep link the student came for. Kept through onboarding and used afterwards. */
  next?: string
  course?: string
  level?: string
}

interface Props {
  search: OnboardingSearch
  /** Moves the URL to another step (`replace` for corrections, so Back does not loop). */
  onStep: (step: string, options?: { replace?: boolean }) => void
  /** Where to go when the flow ends: the deep link or the default, decided by the route. */
  destination: string
}

/**
 * The personalised first-run flow (PRD 5.2, 5.3): one step per screen, the step in the URL, every answer saved on
 * Continue through the owning module, resume at the first unfinished step, then the celebration.
 */
export function OnboardingContainer({ search, onStep, destination }: Props) {
  const router = useRouter()
  const { signOut } = useAuth()
  const boot = useBootstrap()
  const state = useOnboardingState()
  const complete = useCompleteOnboarding()
  const [walk, setWalk] = useState<string[] | null>(null)
  const [celebrating, setCelebrating] = useState(false)
  const slow = useSlow(state.isPending || boot.isPending)

  // The walk is fixed once, when the state first arrives, so the progress bar never shrinks as steps get done.
  useEffect(() => {
    if (state.data && walk === null) setWalk(walkOf(state.data.mode, state.data.steps))
  }, [state.data, walk])

  const resolved = walk && state.data ? resolveStep(walk, state.data.steps, search.step) : null
  const current = resolved?.key ?? null

  // Keep the URL honest: no step, an unknown one, or one past a missing mandatory step is corrected in place.
  useEffect(() => {
    if (current && current !== search.step) onStep(current, { replace: true })
  }, [current, search.step, onStep])

  // Nothing left to do (for example a returning student with no new steps): finish quietly.
  const ready = walk !== null && state.data !== undefined && resolved?.key === null
  useEffect(() => {
    if (ready && !complete.isPending && !complete.isSuccess && !complete.isError) finish()
    // `finish` only reads stable mutation helpers; running it on `ready` is the point.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready])

  function finish() {
    complete.mutate(undefined, {
      onSuccess: (completion) => {
        const version = completion.state.required_version
        track('onboarding_completed', { mode: completion.state.mode })
        if (celebrationSeen(version)) return leave()
        markCelebrated(version)
        setCelebrating(true)
      },
      onError: () => {
        // A step is missing on the server (409) or the call failed: re-read the state and the guard steers back.
        void state.refetch()
      },
    })
  }

  function leave() {
    router.history.push(destination)
  }

  function advance(from: string) {
    if (!walk) return
    const following = nextAfter(walk, from)
    if (following) onStep(following)
    else finish()
  }

  if (celebrating) {
    return (
      <Celebration
        title="You are all set"
        message={celebrationMessage(boot.data?.first_name ?? '', boot.data?.course ?? null)}
        ctaLabel="Open my workspace"
        onContinue={leave}
      />
    )
  }

  if (state.isError || boot.isError) {
    return (
      <LoadErrorPanel
        onRetry={() => {
          void state.refetch()
          void boot.refetch()
        }}
        onSignOut={() => void signOut()}
      />
    )
  }

  if (!state.data || !boot.data || !walk || !current) {
    return (
      <WorkspaceSkeleton slow={slow}>
        {complete.isError ? <Alert variant="error">{describeStepError(complete.error).message}</Alert> : null}
      </WorkspaceSkeleton>
    )
  }

  const copy = copyFor(current)
  const index = walk.indexOf(current)
  const back = previousBefore(walk, current)
  const props: StepProps = { bootstrap: boot.data, onDone: () => advance(current) }
  const returning = state.data.mode === 'update'

  return (
    <PageColumn>
      <StepFlow
        steps={walk.map((key) => copyFor(key).label)}
        current={index}
        title={copy.title}
        description={
          returning && index === 0 ? 'We added a few quick questions to personalise your plan.' : copy.description
        }
        onBack={back ? () => onStep(back) : undefined}
      >
        {current === 'profile' ? <ProfileStep {...props} /> : null}
        {current === 'course' ? (
          <CourseStep {...props} initialCourse={search.course} initialLevel={search.level} />
        ) : null}
        {current === 'hours' ? <HoursStep {...props} /> : null}
        {current === 'targets' ? <TargetsStep {...props} /> : null}
        {current === 'catchup' ? <CatchupStep {...props} /> : null}
        {current === 'avatar' ? <AvatarStep {...props} /> : null}
      </StepFlow>
    </PageColumn>
  )
}
