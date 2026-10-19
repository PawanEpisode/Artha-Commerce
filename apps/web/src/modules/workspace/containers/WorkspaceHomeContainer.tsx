import { Page } from '@artha/design-system'
import { useRef } from 'react'

import { ResultPromptBanner } from '~/modules/progression'

import { useWorkspaceViewed } from '../hooks/useWorkspaceAnalytics'
import { ContinueWidget } from './ContinueWidget'
import { ProgressWidget } from './ProgressWidget'
import { RevisionWidget } from './RevisionWidget'
import { SetupWidget } from './SetupWidget'
import { StatRow } from './StatRow'
import { StudyHeader } from './StudyHeader'
import { TargetsWidget } from './TargetsWidget'
import { ThoughtWidget } from './ThoughtWidget'
import { TodayWidget } from './TodayWidget'

/**
 * /app (PRD 7.3). Every widget loads, fails and hides on its own, so one slow or switched-off feature never blanks
 * the page. Header row, stat row, then a dense grid that fills the width; on a phone the cards stack in that order.
 */
export function WorkspaceHomeContainer() {
  const root = useRef<HTMLDivElement>(null)
  useWorkspaceViewed(root)
  return (
    <Page ref={root}>
      <ResultPromptBanner />
      <StudyHeader />
      <StatRow />
      <div className="grid grid-cols-1 items-stretch gap-3 md:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0">
        <TodayWidget />
        <ContinueWidget />
        <RevisionWidget />
        <ProgressWidget />
        <TargetsWidget />
        <ThoughtWidget />
        <SetupWidget />
      </div>
    </Page>
  )
}
