import { Alert, Badge, Button, Smartphone } from '@artha/design-system'

import { AlertsActions, AlertsCard, SAVE_FAILED } from './AlertsCard'
import { WRAP_BUTTON } from './classes'
import { InstallSteps } from './InstallSteps'

/**
 * iPhone and iPad (iOS 16.4 or later): alerts only work from the Home Screen app, so the step explains the install and
 * lets the student carry on without it. Installed and reopened, the same URL brings them back to this step.
 */
export function InstallGuide({
  finishing,
  finishFailed,
  headingRef,
  onContinue,
}: {
  finishing: boolean
  finishFailed?: boolean
  headingRef?: React.Ref<HTMLHeadingElement>
  onContinue: () => void
}) {
  return (
    <AlertsCard
      id="alerts-install-heading"
      title="Add Artha to your Home Screen first"
      headingRef={headingRef}
      badge={
        <Badge variant="highlight">
          <Smartphone aria-hidden /> Install first
        </Badge>
      }
    >
      <p>On iPhone and iPad, alerts only work from the Home Screen app (iOS 16.4 or later). It takes about a minute.</p>
      <InstallSteps />
      {finishFailed ? <Alert variant="error">{SAVE_FAILED}</Alert> : null}
      <AlertsActions>
        <Button variant="outline" size="lg" loading={finishing} onClick={onContinue} className={WRAP_BUTTON}>
          Continue without alerts
        </Button>
      </AlertsActions>
    </AlertsCard>
  )
}
