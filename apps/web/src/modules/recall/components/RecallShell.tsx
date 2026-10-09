import { Alert, Button, Container, EmptyState, Sparkles } from '@artha/design-system'
import type { ReactNode } from 'react'

import { useRecallEnabled } from '../hooks/useRecallBasics'
import { RouterSectionTabs } from './RouterSectionTabs'

/**
 * Frame for the signed-in recall screens: the `recall_system` flag (fail closed), local navigation and the page width.
 * With the flag off the student sees one honest sentence and nothing else, the same as the API's 404.
 */
export function RecallShell({ children }: { children: ReactNode }) {
  return (
    <RecallGate>
      <RouterSectionTabs />
      <Container className="max-w-3xl space-y-6 py-8 sm:py-12">{children}</Container>
    </RecallGate>
  )
}

/** The flag check alone, for the full-screen review where no tabs or page padding belong. */
export function RecallGate({ children }: { children: ReactNode }) {
  const enabled = useRecallEnabled()
  return enabled ? <>{children}</> : <RecallUnavailable />
}

export function RecallUnavailable() {
  return (
    <Container className="max-w-3xl py-14">
      <EmptyState
        icon={<Sparkles aria-hidden />}
        title="Revision cards are not available yet"
        description="We are rolling them out gradually. Please check back soon."
      />
    </Container>
  )
}

export function LoadError({ onRetry, what }: { onRetry: () => void; what: string }) {
  return (
    <Alert variant="error">
      <span className="flex flex-wrap items-center gap-3">
        We could not load {what}.
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </span>
    </Alert>
  )
}
