import { Alert, Button, Container, EmptyState, Skeleton, Sparkles } from '@artha/design-system'
import { Navigate } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { CoverageNav } from '../components/CoverageNav'
import { useOverview } from '../hooks/useCoverageQueries'
import { useOfflineSync } from '../hooks/useOfflineSync'
import type { Overview } from '../lib/types'

/**
 * Frame for every signed-in My Coverage screen: feature flag, "no enrolment yet" redirect, loading and error states,
 * and the local navigation. Children render only once the overview is loaded.
 */
export function CoverageShell({
  children,
  nav = true,
}: {
  children: (overview: Overview) => ReactNode
  nav?: boolean
}) {
  const enabled = useFeatureFlag('syllabus_coverage')
  const { data, isPending, isError, noEnrollment, featureDisabled, refetch } = useOverview()
  const { pending } = useOfflineSync()

  if (!enabled || featureDisabled) {
    return (
      <Container className="max-w-3xl py-14">
        <EmptyState
          icon={<Sparkles aria-hidden />}
          title="My Coverage is not available yet"
          description="We are rolling it out gradually. Please check back soon."
        />
      </Container>
    )
  }
  if (noEnrollment) return <Navigate to="/app/onboarding" replace />

  return (
    <>
      {nav ? <CoverageNav dueCount={data?.due_count} /> : null}
      <Container className="max-w-3xl space-y-6 py-8 sm:py-12">
        {pending > 0 ? (
          <Alert variant="info">
            <span role="status">
              {pending === 1 ? '1 change is' : `${pending} changes are`} saved on this device and will sync when you are
              back online.
            </span>
          </Alert>
        ) : null}
        {isPending ? (
          <div aria-busy="true" className="space-y-4">
            <span className="sr-only" role="status">
              Loading your coverage…
            </span>
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : isError || !data ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              We could not load your coverage.
              <Button size="sm" variant="outline" onClick={() => void refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          children(data)
        )}
      </Container>
    </>
  )
}
