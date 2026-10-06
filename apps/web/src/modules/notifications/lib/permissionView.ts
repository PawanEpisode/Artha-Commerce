import type { BrowserPermission } from './browser'
import type { Browser, Environment, Platform } from './platform'

/**
 * The one honest answer to "can this device get alerts?", shown by the permission card. Each kind has its own wording;
 * none of them is a switch that does nothing.
 *
 * - `checking`: still asking the browser.
 * - `not_configured`: this build has no VAPID key, so nothing could be sent anyway.
 * - `blocked`: the student (or a browser policy) blocked notifications for this site. We cannot ask again.
 * - `ready`: permission not asked yet; one tap shows the browser prompt.
 * - `granted_no_device`: permission given but this browser is not registered with us (never subscribed, or removed).
 * - `active`: permission given and registered.
 */
export type PermissionView =
  | { kind: 'checking' }
  | { kind: 'unsupported' }
  | { kind: 'in_app_browser'; app: string }
  | { kind: 'ios_needs_install' }
  | { kind: 'not_configured' }
  | { kind: 'blocked' }
  | { kind: 'ready' }
  | { kind: 'granted_no_device' }
  | { kind: 'active' }

export interface PermissionFacts {
  environment: Environment | null
  permission: BrowserPermission
  /** Whether this browser holds a push subscription; null while unknown. */
  subscribed: boolean | null
  vapidConfigured: boolean
}

export function derivePermissionView(facts: PermissionFacts): PermissionView {
  const { environment } = facts
  if (!environment) return { kind: 'checking' }
  if (environment.support === 'in_app_browser')
    return { kind: 'in_app_browser', app: environment.inAppBrowser ?? 'an app' }
  if (environment.support === 'ios_needs_install') return { kind: 'ios_needs_install' }
  if (environment.support === 'unsupported' || facts.permission === 'unsupported') return { kind: 'unsupported' }
  if (!facts.vapidConfigured) return { kind: 'not_configured' }
  if (facts.permission === 'denied') return { kind: 'blocked' }
  if (facts.permission === 'default') return { kind: 'ready' }
  if (facts.subscribed === null) return { kind: 'checking' }
  return facts.subscribed ? { kind: 'active' } : { kind: 'granted_no_device' }
}

/** Two or three taps to undo a block, in the words of the browser the student is using. */
export function unblockSteps(browser: Browser, platform: Platform): string {
  if (platform === 'ios') return 'Open Settings, then Notifications, choose Artha and switch on Allow Notifications.'
  if (browser === 'safari')
    return 'In the Safari menu choose Settings, then Websites, then Notifications, and set this site to Allow.'
  if (browser === 'firefox') {
    return 'Click the permissions icon at the left of the address bar, remove the blocked Notifications entry, then reload.'
  }
  if (platform === 'android') {
    return 'Tap the lock icon next to the address, choose Permissions, then Notifications, and set it to Allow.'
  }
  return 'Click the lock icon at the left of the address bar, set Notifications to Allow, then come back and check again.'
}
