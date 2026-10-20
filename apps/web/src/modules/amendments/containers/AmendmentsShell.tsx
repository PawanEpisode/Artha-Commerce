import { Alert, Button, EmptyState, Page, Skeleton, Sparkles, TooltipProvider } from '@artha/design-system'
import type { ReactNode } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { AmendmentsNav } from '../components/AmendmentsNav'
import { useMySummary } from '../hooks/useMySummary'
import { isFeatureDisabled } from '../lib/api'
import type { MySummary } from '../lib/types'

export function AmendmentsShell({
  children,
  nav = true,
  width = 'fluid',
}: {
  children: ((summary: MySummary) => ReactNode) | ReactNode
  nav?: boolean
  width?: 'fluid' | 'form'
}) {
  const enabled = useFeatureFlag('amendments', { strict: true })
  const { data, isPending, isError, error, refetch } = useMySummary()

  const featureDisabled = isFeatureDisabled(error)

  if (!enabled || featureDisabled) {
    return (
      <Page width="form">
        <EmptyState
          className="rounded-lg py-8"
          icon={<Sparkles aria-hidden />}
          title="Amendments are not available yet"
          description="We are rolling out the statutory and academic amendments engine gradually. Please check back soon."
        />
      </Page>
    )
  }

  return (
    <TooltipProvider>
      {nav ? <AmendmentsNav /> : null}
      <Page width={width}>
        {isPending ? (
          <div aria-busy="true" className="space-y-4">
            <span className="sr-only" role="status">
              Loading your amendments…
            </span>
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-24 w-full" />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
            <Skeleton className="h-40 w-full" />
          </div>
        ) : isError || !data ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center justify-between gap-3">
              <span>We could not load your amendments.</span>
              <Button size="sm" variant="outline" onClick={() => void refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : typeof children === 'function' ? (
          children(data)
        ) : (
          children
        )}
      </Page>
    </TooltipProvider>
  )
}
