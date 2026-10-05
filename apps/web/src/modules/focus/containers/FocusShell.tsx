import { Alert, Button, Container, EmptyState, Skeleton, Sparkles, TooltipProvider } from '@artha/design-system'
import type { ReactNode } from 'react'

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
  children,
}: {
  state: 'loading' | 'error' | 'ready'
  /** The server answered 403 `feature_disabled`. */
  disabled: boolean
  onRetry: () => void
  children: ReactNode
}) {
  const enabled = useFeatureFlag('focus_timer')
  const { pending } = useTrackerSync()

  if (!enabled || disabled) {
    return (
      <Container className="max-w-3xl py-14">
        <EmptyState
          icon={<Sparkles aria-hidden />}
          title="The focus timer is not available yet"
          description="We are rolling it out gradually. Please check back soon."
        />
      </Container>
    )
  }

  return (
    <TooltipProvider>
      <RouterSectionTabs label="Focus timer sections" items={SECTIONS} width="3xl" />
      <Container className="max-w-3xl space-y-6 py-8 sm:py-12">
        {pending > 0 ? (
          <Alert variant="info">
            <span role="status">
              {pending === 1 ? '1 change is' : `${pending} changes are`} saved on this device and will sync when you are
              back online.
            </span>
          </Alert>
        ) : null}
        {state === 'loading' ? (
          <div aria-busy="true" className="space-y-4">
            <span className="sr-only" role="status">
              Loading the focus timer…
            </span>
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : state === 'error' ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              We could not load the focus timer.
              <Button variant="outline" onClick={onRetry}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          children
        )}
      </Container>
    </TooltipProvider>
  )
}
