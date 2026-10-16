import { Alert, Button, EmptyState, Page, Skeleton, Sparkles } from '@artha/design-system'
import type { ComponentProps, ReactNode } from 'react'

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
export function TrackerShell({
  children,
  width = 'fluid',
  tabs = true,
}: {
  children: (tz: string, weekStart: 0 | 1) => ReactNode
  width?: ComponentProps<typeof Page>['width']
  /** Settings live in the settings area, which has its own side list, so they drop the local tabs. */
  tabs?: boolean
}) {
  const enabled = useFeatureFlag('time_tracker')
  const settings = useTrackerSettings()
  const { pending } = useTrackerSync()

  if (!enabled || isFeatureDisabled(settings.error)) {
    return (
      <Page width="form">
        <EmptyState
          className="rounded-lg py-6"
          icon={<Sparkles aria-hidden />}
          title="The time tracker is not available yet"
          description="We are rolling it out gradually. Please check back soon."
        />
      </Page>
    )
  }

  return (
    <>
      {tabs ? <RouterSectionTabs label="Time tracker sections" items={TRACKER_SECTIONS} /> : null}
      <Page width={width}>
        {pending > 0 ? (
          <Alert variant="info">
            <span role="status">
              {pending === 1 ? '1 change is' : `${pending} changes are`} saved on this device and will sync when you are
              back online.
            </span>
          </Alert>
        ) : null}
        {settings.isPending ? (
          <div aria-busy="true" className="space-y-3">
            <span className="sr-only" role="status">
              Loading the time tracker…
            </span>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : settings.isError || !settings.data ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              We could not load the time tracker.
              <Button variant="outline" size="sm" onClick={() => void settings.refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          children(settings.data.tz, settings.data.week_start)
        )}
      </Page>
    </>
  )
}
