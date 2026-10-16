import { Alert, Button, EmptyState, Page, Skeleton, Sparkles } from '@artha/design-system'
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
  width = 'fluid',
}: {
  children: (overview: Overview) => ReactNode
  nav?: boolean
  /** `form` keeps settings and forms at a readable width. */
  width?: 'fluid' | 'form'
}) {
  const enabled = useFeatureFlag('syllabus_coverage')
  const { data, isPending, isError, noEnrollment, featureDisabled, refetch } = useOverview()
  const { pending } = useOfflineSync()

  if (!enabled || featureDisabled) {
    return (
      <Page width="form">
        <EmptyState
          className="rounded-lg py-6"
          icon={<Sparkles aria-hidden />}
          title="My Coverage is not available yet"
          description="We are rolling it out gradually. Please check back soon."
        />
      </Page>
    )
  }
  if (noEnrollment) return <Navigate to="/app/onboarding" replace />

  return (
    <>
      {nav ? <CoverageNav dueCount={data?.due_count} /> : null}
      <Page width={width}>
        {pending > 0 ? (
          <Alert variant="info">
            <span role="status">
              {pending === 1 ? '1 change is' : `${pending} changes are`} saved on this device and will sync when you are
              back online.
            </span>
          </Alert>
        ) : null}
        {isPending ? (
          <div aria-busy="true" className="space-y-3">
            <span className="sr-only" role="status">
              Loading your coverage…
            </span>
            <Skeleton className="h-7 w-48" />
            <Skeleton className="h-16 w-full max-w-4xl" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
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
      </Page>
    </>
  )
}
