import { Alert, Badge, Button, CircleAlert, Copy } from '@artha/design-system'

import { AlertsActions, AlertsCard, SAVE_FAILED } from './AlertsCard'
import { WRAP_BUTTON } from './classes'

/** Opened inside WhatsApp, Instagram and the like: alerts cannot work there, so send the student to a real browser. */
export function InAppBrowserCard({
  app,
  finishing,
  finishFailed,
  headingRef,
  onCopyLink,
  onContinue,
}: {
  app: string
  finishing: boolean
  finishFailed?: boolean
  headingRef?: React.Ref<HTMLHeadingElement>
  onCopyLink: () => void
  onContinue: () => void
}) {
  return (
    <AlertsCard
      id="alerts-inapp-heading"
      title="Open Artha in your browser"
      headingRef={headingRef}
      badge={
        <Badge variant="highlight">
          <CircleAlert aria-hidden /> Not here
        </Badge>
      }
    >
      <p>
        You opened Artha inside {app}. Alerts cannot work in a browser built into another app. Open this page in Chrome
        or Safari and this step will be waiting for you.
      </p>
      <ol className="list-decimal space-y-2 pl-5 marker:font-semibold">
        <li>Copy the link below.</li>
        <li>Open Chrome or Safari and paste it into the address bar.</li>
      </ol>
      <p className="text-sm text-muted-foreground">
        Or use the menu or share button of {app} and choose Open in browser.
      </p>
      {finishFailed ? <Alert variant="error">{SAVE_FAILED}</Alert> : null}
      <AlertsActions>
        <Button variant="cta" size="lg" onClick={onCopyLink} disabled={finishing} className={WRAP_BUTTON}>
          <Copy aria-hidden /> Copy link
        </Button>
        <Button variant="ghost" size="lg" loading={finishing} onClick={onContinue} className={WRAP_BUTTON}>
          Continue without alerts
        </Button>
      </AlertsActions>
    </AlertsCard>
  )
}
