import { Alert, Badge, BellRing, Button, CircleAlert, CircleCheck, Lock } from '@artha/design-system'
import type { ReactNode } from 'react'

import { AlertsActions, AlertsCard, SAVE_FAILED } from './AlertsCard'
import { WRAP_BUTTON } from './classes'

export type OutcomeKind = 'on' | 'denied' | 'dismissed' | 'device_limit' | 'unsupported' | 'not_configured'

interface Copy {
  title: string
  badge: ReactNode
  body: string
}

/** Icon plus words for every status, never colour alone. The tick only animates when the student allows motion. */
const COPY: Record<OutcomeKind, Copy> = {
  on: {
    title: 'Alerts are on',
    badge: (
      <Badge variant="accent">
        <CircleCheck aria-hidden className="motion-safe:animate-in motion-safe:duration-300 motion-safe:zoom-in-50" />{' '}
        On
      </Badge>
    ),
    body: 'You will hear when a focus round or a break ends, even when Artha is closed. Send yourself a test to see how it looks.',
  },
  denied: {
    title: 'Alerts are off',
    badge: (
      <Badge variant="outline">
        <Lock aria-hidden /> Off
      </Badge>
    ),
    body: 'You chose not to allow alerts, and that is fine. Your timer, chime and tab title still work. If you change your mind, Settings shows how to turn them on.',
  },
  dismissed: {
    title: 'No problem',
    badge: <Badge variant="outline">Off</Badge>,
    body: 'The prompt closed without an answer. You can turn alerts on any time from Settings.',
  },
  device_limit: {
    title: 'You have too many devices',
    badge: (
      <Badge variant="highlight">
        <CircleAlert aria-hidden /> Limit reached
      </Badge>
    ),
    body: 'Your browser allows alerts, but this device could not be added because you already have the most devices we allow. Remove one in Settings, then turn alerts on here.',
  },
  unsupported: {
    title: 'This browser cannot show alerts',
    badge: <Badge variant="outline">Not available</Badge>,
    body: 'Your timer, chime and tab title still work. A recent Chrome, Edge, Firefox or Safari can show alerts.',
  },
  not_configured: {
    title: 'Alerts are not ready yet',
    badge: <Badge variant="outline">Not available</Badge>,
    body: 'Alerts are not set up in this version of Artha yet. Nothing is wrong with your device, and you can come back to this later.',
  },
}

/** The end of a branch: what happened, and Continue. `on` also carries the test button (FR-N11) as `children`. */
export function AlertsOutcomeCard({
  kind,
  finishing,
  finishFailed,
  headingRef,
  onContinue,
  onRetry,
  children,
}: {
  kind: OutcomeKind
  finishing: boolean
  finishFailed?: boolean
  headingRef?: React.Ref<HTMLHeadingElement>
  onContinue: () => void
  /** `dismissed` only: ask the browser again. */
  onRetry?: () => void
  children?: ReactNode
}) {
  const { title, badge, body } = COPY[kind]
  return (
    <AlertsCard id="alerts-outcome-heading" title={title} badge={badge} headingRef={headingRef}>
      <p>{body}</p>
      {children}
      {finishFailed ? <Alert variant="error">{SAVE_FAILED}</Alert> : null}
      <AlertsActions>
        <Button variant="cta" size="lg" loading={finishing} onClick={onContinue}>
          Continue
        </Button>
        {kind === 'dismissed' && onRetry ? (
          <Button variant="outline" size="lg" disabled={finishing} onClick={onRetry} className={WRAP_BUTTON}>
            <BellRing aria-hidden /> Turn on alerts after all
          </Button>
        ) : null}
      </AlertsActions>
    </AlertsCard>
  )
}
