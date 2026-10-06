import { Alert, BellRing, Button } from '@artha/design-system'

import { AlertPreview } from './AlertPreview'
import { AlertsActions, AlertsCard, SAVE_FAILED } from './AlertsCard'
import { WRAP_BUTTON } from './classes'

interface Props {
  /** `finish_setup`: the browser already allows alerts, so no prompt will show. */
  mode: 'prompt' | 'finish_setup'
  /** The browser prompt is open or the device is being registered. */
  enabling: boolean
  /** Saving "Not now" is in flight. */
  finishing: boolean
  enableError?: string | null
  finishFailed?: boolean
  headingRef?: React.Ref<HTMLHeadingElement>
  onEnable: () => void
  onNotNow: () => void
}

/**
 * The pre-prompt (PRD 5.1): a page, not a modal that traps focus. It says what we send and why, that it can be turned
 * off at any time (consent, FR-N26), and shows the alert. The browser's own prompt appears only after the button.
 */
export function AlertsPreCard({
  mode,
  enabling,
  finishing,
  enableError,
  finishFailed,
  headingRef,
  onEnable,
  onNotNow,
}: Props) {
  const prompt = mode === 'prompt'
  return (
    <AlertsCard
      id="alerts-pre-heading"
      title={prompt ? 'Hear when your round ends' : 'One more tap to finish'}
      headingRef={headingRef}
    >
      <p>
        {prompt
          ? 'Alerts tell you when a focus round or a break ends, even when Artha is closed or in the background. That is all we send for now: no marketing, and nothing you did not choose.'
          : 'Your browser already allows alerts. Set up this device so they reach you when a round ends.'}
      </p>
      <AlertPreview />
      <p className="text-sm text-muted-foreground">
        {prompt
          ? 'Your browser will ask for permission once. You can turn alerts off any time in Settings, and each device can be removed.'
          : 'You can turn alerts off any time in Settings, and each device can be removed.'}
      </p>
      {enableError ? <Alert variant="error">{enableError}</Alert> : null}
      {finishFailed ? <Alert variant="error">{SAVE_FAILED}</Alert> : null}
      <AlertsActions>
        <Button
          variant="cta"
          size="lg"
          loading={enabling}
          disabled={finishing}
          onClick={onEnable}
          className={WRAP_BUTTON}
        >
          <BellRing aria-hidden /> {prompt ? 'Turn on alerts' : 'Set up this device'}
        </Button>
        <Button variant="ghost" size="lg" loading={finishing} disabled={enabling} onClick={onNotNow}>
          Not now
        </Button>
      </AlertsActions>
    </AlertsCard>
  )
}
