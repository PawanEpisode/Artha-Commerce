import {
  Alert,
  Button,
  Container,
  EmptyState,
  Skeleton,
  Sparkles,
  ToastProvider,
  TooltipProvider,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { useTrackerSync } from '~/modules/tracker'

const ITEMS = [
  { to: '/app/focus', label: 'Timer', exact: true },
  { to: '/app/focus/history', label: 'History', exact: false },
  { to: '/app/settings/focus', label: 'Settings', exact: false },
  { to: '/app/tracker', label: 'Time tracker', exact: false },
] as const

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
    <ToastProvider>
      <TooltipProvider>
        <Container className="max-w-3xl space-y-6 py-10 sm:py-14">
          <nav aria-label="Focus timer" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
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
                {pending === 1 ? '1 change is' : `${pending} changes are`} saved on this device and will sync when you
                are back online.
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
                <Button size="sm" variant="outline" onClick={onRetry}>
                  Try again
                </Button>
              </span>
            </Alert>
          ) : (
            children
          )}
        </Container>
      </TooltipProvider>
    </ToastProvider>
  )
}
