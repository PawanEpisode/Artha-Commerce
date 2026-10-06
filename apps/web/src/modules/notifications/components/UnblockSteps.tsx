import { Alert, Badge, Button, Lock, RefreshCw } from '@artha/design-system'

import { unblockSteps } from '../lib/permissionView'
import type { Browser, Platform } from '../lib/platform'
import { AlertsActions, AlertsCard, SAVE_FAILED } from './AlertsCard'

/** Alerts were already blocked for this site: how to undo it in this browser, a way to check, and a way to move on. */
export function UnblockSteps({
  browser,
  platform,
  checks,
  checking,
  finishing,
  finishFailed,
  headingRef,
  onCheckAgain,
  onSkip,
}: {
  browser: Browser
  platform: Platform
  /** How many times "Check again" has run: after one, a still-blocked answer is said out loud. */
  checks: number
  checking: boolean
  finishing: boolean
  finishFailed?: boolean
  headingRef?: React.Ref<HTMLHeadingElement>
  onCheckAgain: () => void
  onSkip: () => void
}) {
  return (
    <AlertsCard
      id="alerts-blocked-heading"
      title="Alerts are blocked for this site"
      headingRef={headingRef}
      badge={
        <Badge variant="highlight">
          <Lock aria-hidden /> Blocked
        </Badge>
      }
    >
      <p>We cannot ask again while they are blocked. You can allow them yourself:</p>
      <p className="font-medium">{unblockSteps(browser, platform)}</p>
      {checks > 0 && !checking ? (
        <p className="text-sm text-muted-foreground">
          Still blocked. Allow notifications for this site, then check again.
        </p>
      ) : null}
      {finishFailed ? <Alert variant="error">{SAVE_FAILED}</Alert> : null}
      <AlertsActions>
        <Button variant="cta" size="lg" loading={checking} disabled={finishing} onClick={onCheckAgain}>
          <RefreshCw aria-hidden /> Check again
        </Button>
        <Button variant="ghost" size="lg" loading={finishing} disabled={checking} onClick={onSkip}>
          Skip for now
        </Button>
      </AlertsActions>
    </AlertsCard>
  )
}
