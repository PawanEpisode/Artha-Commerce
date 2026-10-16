import { Alert, Button, EmptyState, Page, Sparkles } from '@artha/design-system'
import type { ComponentProps, ReactNode } from 'react'

import { useRecallEnabled } from '../hooks/useRecallBasics'
import { RouterSectionTabs } from './RouterSectionTabs'

/**
 * Frame for the signed-in recall screens: the `recall_system` flag (fail closed), local navigation and the page body.
 * Data screens use the full width; forms and settings pass `width="form"`.
 * With the flag off the student sees one honest sentence and nothing else, the same as the API's 404.
 */
export function RecallShell({
  children,
  width = 'fluid',
  tabs = true,
}: {
  children: ReactNode
  width?: ComponentProps<typeof Page>['width']
  /** Settings pages live in the settings area, which has its own side list, so they drop the local tabs. */
  tabs?: boolean
}) {
  return (
    <RecallGate>
      {tabs ? <RouterSectionTabs /> : null}
      <Page width={width}>{children}</Page>
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
    <Page width="form">
      <EmptyState
        className="rounded-lg py-6"
        icon={<Sparkles aria-hidden />}
        title="Revision cards are not available yet"
        description="We are rolling them out gradually. Please check back soon."
      />
    </Page>
  )
}

export function LoadError({ onRetry, what }: { onRetry: () => void; what: string }) {
  return (
    <Alert variant="error">
      <span className="flex flex-wrap items-center gap-3">
        We could not load {what}.
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </span>
    </Alert>
  )
}
