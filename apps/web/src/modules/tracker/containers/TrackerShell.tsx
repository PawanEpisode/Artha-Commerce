import { Alert, Button, Container, EmptyState, Skeleton, Sparkles } from '@artha/design-system'
import type { ReactNode } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { RouterSectionTabs } from '../components/RouterSectionTabs'
import { useTrackerSettings } from '../hooks/useTrackerQueries'
import { useTrackerSync } from '../hooks/useTrackerSync'
import { isFeatureDisabled } from '../lib/api'
import { TRACKER_SECTIONS } from '../lib/sections'

/**
 * Frame for every signed-in tracker screen: the `time_tracker` flag (web and server), the offline banner, local
 * navigation, loading and error states. Children render once the student's tracker settings (time zone) are known.
 */
export function TrackerShell({ children }: { children: (tz: string, weekStart: 0 | 1) => ReactNode }) {
  const enabled = useFeatureFlag('time_tracker')
  const settings = useTrackerSettings()
  const { pending } = useTrackerSync()

  if (!enabled || isFeatureDisabled(settings.error)) {
    return (
      <Container className="max-w-3xl py-14">
        <EmptyState
          icon={<Sparkles aria-hidden />}
          title="The time tracker is not available yet"
          description="We are rolling it out gradually. Please check back soon."
        />
      </Container>
    )
  }

  return (
    <>
      <RouterSectionTabs label="Time tracker sections" items={TRACKER_SECTIONS} />
      <Container className="max-w-4xl space-y-6 py-8 sm:py-12">
        {pending > 0 ? (
          <Alert variant="info">
            <span role="status">
              {pending === 1 ? '1 change is' : `${pending} changes are`} saved on this device and will sync when you are
              back online.
            </span>
          </Alert>
        ) : null}
        {settings.isPending ? (
          <div aria-busy="true" className="space-y-4">
            <span className="sr-only" role="status">
              Loading the time tracker…
            </span>
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : settings.isError || !settings.data ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              We could not load the time tracker.
              <Button variant="outline" onClick={() => void settings.refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          children(settings.data.tz, settings.data.week_start)
        )}
      </Container>
    </>
  )
}
