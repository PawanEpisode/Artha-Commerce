import { Alert, Button, EmptyState, Page, Skeleton, Sparkles, TooltipProvider } from '@artha/design-system'
import type { ComponentProps, ReactNode } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { RouterSectionTabs, type SectionLink, useTrackerSync } from '~/modules/tracker'

const SECTIONS: ReadonlyArray<SectionLink> = [
  { value: 'timer', label: 'Timer', to: '/app/focus' },
  { value: 'history', label: 'History', to: '/app/focus/history' },
  { value: 'settings', label: 'Settings', to: '/app/settings/focus' },
  { value: 'tracker', label: 'Time tracker', to: '/app/tracker' },
]

/**
 * Frame for every focus screen: the `focus_timer` flag (web), the offline banner, local navigation and the loading and
 * error states. `state` tells the shell what the screen's main query is doing.
 */
export function FocusShell({
  state,
  disabled,
  onRetry,
  width = 'fluid',
  tabs = true,
  children,
}: {
  state: 'loading' | 'error' | 'ready'
  /** The server answered 403 `feature_disabled`. */
  disabled: boolean
  onRetry: () => void
  width?: ComponentProps<typeof Page>['width']
  /** Settings live in the settings area, which has its own side list, so they drop the local tabs. */
  tabs?: boolean
  children: ReactNode
}) {
  const enabled = useFeatureFlag('focus_timer')
  const { pending } = useTrackerSync()

  if (!enabled || disabled) {
    return (
      <Page width="form">
        <EmptyState
          className="rounded-lg py-6"
          icon={<Sparkles aria-hidden />}
          title="The focus timer is not available yet"
          description="We are rolling it out gradually. Please check back soon."
        />
      </Page>
    )
  }

  return (
    <TooltipProvider>
      {tabs ? <RouterSectionTabs label="Focus timer sections" items={SECTIONS} /> : null}
      <Page width={width}>
        {pending > 0 ? (
          <Alert variant="info">
            <span role="status">
              {pending === 1 ? '1 change is' : `${pending} changes are`} saved on this device and will sync when you are
              back online.
            </span>
          </Alert>
        ) : null}
        {state === 'loading' ? (
          <div aria-busy="true" className="space-y-3">
            <span className="sr-only" role="status">
              Loading the focus timer…
            </span>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-80 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : state === 'error' ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              We could not load the focus timer.
              <Button variant="outline" size="sm" onClick={onRetry}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          children
        )}
      </Page>
    </TooltipProvider>
  )
}
