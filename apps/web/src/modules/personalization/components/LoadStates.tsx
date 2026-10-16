import { Alert, Button, Skeleton } from '@artha/design-system'
import type { ReactNode } from 'react'

/** Centered page column shared by the loading, error and onboarding screens. */
export function PageColumn({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-xl min-w-0 px-4 py-6 sm:py-10">{children}</div>
}

/** Placeholder while the bootstrap or the onboarding state loads. `slow` adds a calm "still working" line. */
export function WorkspaceSkeleton({ slow = false, children }: { slow?: boolean; children?: ReactNode }) {
  return (
    <PageColumn>
      <div className="space-y-4" aria-busy role="status" aria-label="Loading your workspace">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-48 w-full" />
        {slow ? <p className="text-[13px] text-muted-foreground">This is taking longer than usual…</p> : null}
        {children}
      </div>
    </PageColumn>
  )
}

/** The API could not be reached for something the student cannot continue without. Retry, or leave. */
export function LoadErrorPanel({ onRetry, onSignOut }: { onRetry: () => void; onSignOut: () => void }) {
  return (
    <PageColumn>
      <Alert variant="error">
        <div className="space-y-2">
          <p>We could not load your workspace. Check your connection and try again.</p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={onRetry}>
              Try again
            </Button>
            <Button size="sm" variant="outline" onClick={onSignOut}>
              Sign out
            </Button>
          </div>
        </div>
      </Alert>
    </PageColumn>
  )
}
