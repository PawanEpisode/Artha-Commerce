import { Alert, Badge, Button, Share, Smartphone, SquarePlus } from '@artha/design-system'

import { AlertsActions, AlertsCard, SAVE_FAILED } from './AlertsCard'
import { WRAP_BUTTON } from './classes'

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
      <ol className="list-decimal space-y-3 pl-5 marker:font-semibold">
        <li>
          Open this page in Safari and tap the Share button{' '}
          <Share aria-hidden className="inline size-4 align-text-bottom" /> at the bottom of the screen.
        </li>
        <li>
          Scroll down and choose <strong>Add to Home Screen</strong>{' '}
          <SquarePlus aria-hidden className="inline size-4 align-text-bottom" />, then tap Add.
        </li>
        <li>Open Artha from your Home Screen. This page will be right here, ready for the last tap.</li>
      </ol>
      {finishFailed ? <Alert variant="error">{SAVE_FAILED}</Alert> : null}
      <AlertsActions>
        <Button variant="outline" size="lg" loading={finishing} onClick={onContinue} className={WRAP_BUTTON}>
          Continue without alerts
        </Button>
      </AlertsActions>
    </AlertsCard>
  )
}
