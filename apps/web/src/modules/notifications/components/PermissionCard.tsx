import { Badge, BellRing, Button, CircleAlert, CircleCheck, Lock, RefreshCw, Smartphone } from '@artha/design-system'
import type { ReactNode } from 'react'

import type { PermissionView } from '../lib/permissionView'
import { unblockSteps } from '../lib/permissionView'
import type { Browser, Platform } from '../lib/platform'
import { WRAP_BUTTON as WRAP } from './classes'

interface Props {
  view: PermissionView
  browser: Browser
  platform: Platform
  /** The enable request is in flight (the browser prompt may be open). */
  busy: boolean
  onEnable: () => void
  onCheckAgain: () => void
}

/**
 * What alerts on THIS device look like right now, in plain words. Every state says what is true and what the student
 * can do about it; none of them is a control that silently does nothing. Status is icon plus text, never colour alone.
 */
export function PermissionCard({ view, browser, platform, busy, onEnable, onCheckAgain }: Props) {
  const { badge, body, action } = describe(view, { browser, platform, busy, onEnable, onCheckAgain })
  return (
    <section aria-labelledby="this-device-heading" className="space-y-3 rounded-2xl border border-border bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="this-device-heading" className="text-lg font-bold">
          This device
        </h2>
        {badge}
      </div>
      {/* One persistent polite region: its text changes as the browser answers. */}
      <div role="status" aria-live="polite" className="text-sm text-muted-foreground">
        {body}
      </div>
      {action ? <div className="flex flex-wrap gap-3">{action}</div> : null}
    </section>
  )
}

interface Actions {
  browser: Browser
  platform: Platform
  busy: boolean
  onEnable: () => void
  onCheckAgain: () => void
}

function describe(view: PermissionView, a: Actions): { badge: ReactNode; body: ReactNode; action?: ReactNode } {
  switch (view.kind) {
    case 'checking':
      return { badge: <Badge variant="outline">Checking</Badge>, body: 'Checking what this device allows…' }
    case 'active':
      return {
        badge: (
          <Badge variant="accent">
            <CircleCheck aria-hidden /> On
          </Badge>
        ),
        body: 'Alerts are on for this device. They appear even when Artha is closed or in the background.',
      }
    case 'ready':
      return {
        badge: <Badge variant="outline">Off</Badge>,
        body: 'Turn on alerts to hear when a focus round ends, even when Artha is in the background. Your browser will ask for permission once.',
        action: (
          <Button variant="cta" loading={a.busy} onClick={a.onEnable} className={WRAP}>
            <BellRing aria-hidden /> Turn on alerts on this device
          </Button>
        ),
      }
    case 'granted_no_device':
      return {
        badge: <Badge variant="outline">Not set up</Badge>,
        body: 'Your browser allows alerts, but this device is not set up with us yet. One tap finishes it.',
        action: (
          <Button variant="cta" loading={a.busy} onClick={a.onEnable} className={WRAP}>
            <BellRing aria-hidden /> Set up this device
          </Button>
        ),
      }
    case 'blocked':
      return {
        badge: (
          <Badge variant="highlight">
            <Lock aria-hidden /> Blocked
          </Badge>
        ),
        body: (
          <>
            <p>Alerts are blocked for this site, so we cannot ask again. You can allow them yourself:</p>
            <p className="mt-2 text-foreground">{unblockSteps(a.browser, a.platform)}</p>
          </>
        ),
        action: (
          <Button variant="outline" onClick={a.onCheckAgain}>
            <RefreshCw aria-hidden /> Check again
          </Button>
        ),
      }
    case 'ios_needs_install':
      return {
        badge: (
          <Badge variant="highlight">
            <Smartphone aria-hidden /> Install first
          </Badge>
        ),
        body: (
          <>
            <p>On iPhone and iPad, alerts only work from the Home Screen app (iOS 16.4 or later).</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-foreground">
              <li>Open this page in Safari and tap the Share button.</li>
              <li>Choose Add to Home Screen.</li>
              <li>Open Artha from your Home Screen, then come back to this page.</li>
            </ol>
          </>
        ),
      }
    case 'in_app_browser':
      return {
        badge: (
          <Badge variant="highlight">
            <CircleAlert aria-hidden /> Not here
          </Badge>
        ),
        body: `You opened Artha inside ${view.app}, where alerts cannot work. Open this page in Chrome or Safari, then come back to turn them on.`,
      }
    case 'unsupported':
      return {
        badge: <Badge variant="outline">Not available</Badge>,
        body: 'This browser cannot show alerts. Your timer, chime and the tab title still work. A recent Chrome, Edge, Firefox or Safari can show them.',
      }
    case 'not_configured':
      return {
        badge: <Badge variant="outline">Not available</Badge>,
        body: 'Alerts are not set up in this version of Artha yet. Nothing is wrong with your device.',
      }
  }
}
