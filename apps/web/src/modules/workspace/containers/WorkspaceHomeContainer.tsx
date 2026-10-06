import { Container } from '@artha/design-system'

import { ToolsAndSettings } from '~/modules/layout'

import { ContinueWidget } from './ContinueWidget'
import { ProgressWidget } from './ProgressWidget'
import { RevisionWidget } from './RevisionWidget'
import { SetupWidget } from './SetupWidget'
import { StudyHeader } from './StudyHeader'
import { TodayWidget } from './TodayWidget'

/**
 * /app (PRD 7.3). Every widget loads, fails and hides on its own, so one slow or switched-off feature never blanks
 * the page. Order follows the PRD; on a phone the cards stack in that same order.
 */
export function WorkspaceHomeContainer() {
  return (
    <Container className="space-y-8 py-8 sm:py-12">
      <StudyHeader />
      <div className="grid items-stretch gap-4 lg:grid-cols-2">
        <TodayWidget />
        <ContinueWidget />
        <RevisionWidget />
        <ProgressWidget />
        <SetupWidget />
      </div>
      <ToolsAndSettings />
    </Container>
  )
}
