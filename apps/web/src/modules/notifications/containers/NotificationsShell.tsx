import { Alert, Bell, Button, Container, EmptyState, Skeleton } from '@artha/design-system'
import type { ReactNode } from 'react'

import { useFeatureFlag } from '~/modules/observability'

/**
 * Frame for the notification settings: the page's one `h1`, the `notifications_ui` flag (web), and the loading and
 * error states of the main query. The flag fails open like every other flag; only an explicit off hides the screen.
 */
export function NotificationsShell({
  state,
  disabled,
  onRetry,
  children,
}: {
  state: 'loading' | 'error' | 'ready'
  /** The server answered 403 `notifications_disabled`. */
  disabled: boolean
  onRetry: () => void
  children: ReactNode
}) {
  const enabled = useFeatureFlag('notifications_ui')
  const off = !enabled || disabled

  return (
    <Container className="max-w-3xl space-y-6 py-8 sm:py-12">
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Notifications</h1>
        {off ? null : (
          <p className="text-muted-foreground">Choose what Artha tells you, and when. Changes save as you make them.</p>
        )}
      </header>
      {off ? (
        <EmptyState
          icon={<Bell aria-hidden />}
          title="Notifications are not available yet"
          description="We are rolling them out gradually. Everything else in Artha works as usual. Please check back soon."
        />
      ) : state === 'loading' ? (
        <div aria-busy="true" className="space-y-4">
          <span className="sr-only" role="status">
            Loading your notification settings…
          </span>
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : state === 'error' ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            We could not load your notification settings.
            <Button variant="outline" onClick={onRetry}>
              Try again
            </Button>
          </span>
        </Alert>
      ) : (
        children
      )}
    </Container>
  )
}
