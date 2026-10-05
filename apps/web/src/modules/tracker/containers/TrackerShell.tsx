import { Alert, Button, Container, EmptyState, Skeleton, Sparkles, ToastProvider } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { useTrackerSettings } from '../hooks/useTrackerQueries'
import { useTrackerSync } from '../hooks/useTrackerSync'
import { isFeatureDisabled } from '../lib/api'

const ITEMS = [
  { to: '/app/tracker', label: 'Today', exact: true },
  { to: '/app/tracker/reports', label: 'Reports', exact: false },
  { to: '/app/tracker/log', label: 'Log', exact: false },
  { to: '/app/tracker/goals', label: 'Goals', exact: false },
  { to: '/app/focus', label: 'Focus timer', exact: false },
  { to: '/app/settings/tracker', label: 'Settings', exact: false },
] as const

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
    <ToastProvider>
      <Container className="max-w-4xl space-y-6 py-10 sm:py-14">
        <nav aria-label="Time tracker" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
          {ITEMS.map((item) => (
            <Button key={item.to} variant="ghost" size="sm" className="shrink-0" asChild>
              <Link
                to={item.to}
                activeOptions={{ exact: item.exact }}
                activeProps={{ className: 'bg-secondary text-secondary-foreground', 'aria-current': 'page' }}
              >
                {item.label}
              </Link>
            </Button>
          ))}
        </nav>
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
              <Button size="sm" variant="outline" onClick={() => void settings.refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          children(settings.data.tz, settings.data.week_start)
        )}
      </Container>
    </ToastProvider>
  )
}
