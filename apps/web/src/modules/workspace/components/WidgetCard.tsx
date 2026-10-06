import { Alert, Badge, Button, Card, Skeleton } from '@artha/design-system'
import type { ReactNode } from 'react'

export type WidgetState = 'loading' | 'error' | 'ready'

interface Props {
  title: string
  /** Heading id target for `aria-labelledby`. */
  id: string
  state: WidgetState
  onRetry?: () => void
  /** Shown over cached data while the device is offline. */
  offline?: boolean
  /** Reserves the card's height while loading so nothing jumps when data arrives. */
  skeletonHeight?: string
  className?: string
  children: ReactNode
}

/**
 * The frame every home widget shares: its own heading, skeleton, error with Retry, and offline badge (PRD 7.3).
 * One widget failing never touches the others.
 */
export function WidgetCard({
  title,
  id,
  state,
  onRetry,
  offline,
  skeletonHeight = 'h-36',
  className,
  children,
}: Props) {
  return (
    <Card className={className}>
      <section aria-labelledby={id} className="flex h-full flex-col gap-4 p-5 sm:p-6" aria-busy={state === 'loading'}>
        <div className="flex items-center justify-between gap-2">
          <h2 id={id} className="text-base font-bold">
            {title}
          </h2>
          {offline && state === 'ready' ? <Badge>Offline</Badge> : null}
        </div>
        {state === 'loading' ? (
          <div className="space-y-3" role="status" aria-label={`Loading ${title}`}>
            <Skeleton className={`${skeletonHeight} w-full`} />
          </div>
        ) : state === 'error' ? (
          <Alert variant="error">
            <div className="space-y-2">
              <p>We could not load this.</p>
              {onRetry ? (
                <Button size="sm" variant="outline" onClick={onRetry}>
                  Try again
                </Button>
              ) : null}
            </div>
          </Alert>
        ) : (
          children
        )}
      </section>
    </Card>
  )
}
