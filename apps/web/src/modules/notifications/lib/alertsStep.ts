import type { EnableOutcome } from './enable'
import type { PermissionView } from './permissionView'
import type { PermissionState } from './schemas'

/**
 * The branches of the onboarding step `alerts` (PRD 5.1) as pure functions, so every row of the flowchart is a unit
 * test. The container only reads the browser, runs the effects and renders the card this module names.
 */

/** What the step reports when it is finished (PRD 10 `result`). `blocked` = already blocked on arrival. */
export type AlertsResult = 'granted' | 'denied' | 'dismissed' | 'skipped_install' | 'blocked' | 'unsupported'

/** What the student just did that overrides what the browser reports (the browser may need a moment to catch up). */
export type AfterEnable = 'enabled' | 'denied' | 'dismissed' | 'device_limit' | null

export type AlertsBranch =
  | 'checking'
  | 'in_app_browser'
  | 'install'
  | 'unsupported'
  | 'not_configured'
  | 'blocked'
  | 'pre_prompt'
  | 'finish_setup'
  | 'on'
  | 'denied'
  | 'dismissed'
  | 'device_limit'

export function alertsBranch(view: PermissionView, after: AfterEnable): AlertsBranch {
  if (after === 'enabled') return 'on'
  if (after) return after
  switch (view.kind) {
    case 'checking':
      return 'checking'
    case 'in_app_browser':
      return 'in_app_browser'
    case 'ios_needs_install':
      return 'install'
    case 'unsupported':
      return 'unsupported'
    case 'not_configured':
      return 'not_configured'
    case 'blocked':
      return 'blocked'
    case 'ready':
      return 'pre_prompt'
    case 'granted_no_device':
      return 'finish_setup'
    case 'active':
      return 'on'
  }
}

/**
 * The result a branch finishes with. Null when the branch cannot be finished by a student decision: still `checking`,
 * or `not_configured` (this build cannot send, so nothing is recorded and the step is simply skipped).
 */
export function resultFor(branch: AlertsBranch): AlertsResult | null {
  switch (branch) {
    case 'on':
    case 'device_limit':
      return 'granted'
    case 'denied':
      return 'denied'
    case 'blocked':
      return 'blocked'
    case 'install':
      return 'skipped_install'
    case 'unsupported':
      return 'unsupported'
    case 'pre_prompt':
    case 'finish_setup':
    case 'in_app_browser':
    case 'dismissed':
      return 'dismissed'
    case 'checking':
    case 'not_configured':
      return null
  }
}

/** The state the API stores. A block we found on arrival is stored as `denied`; analytics keeps the finer `blocked`. */
export const stateFor = (result: AlertsResult): PermissionState => (result === 'blocked' ? 'denied' : result)

/**
 * Our own pre-prompt counts as an ask (the API caps asks, so follow-ups stay bounded). Recorded once, and only when the
 * server has not recorded one yet, so revisiting the step never inflates the count.
 */
export const shouldRecordPrePrompt = (branch: AlertsBranch, serverState: PermissionState | undefined): boolean =>
  branch === 'pre_prompt' && serverState === 'not_asked'

/** The step tells a student alerts are on only when they really are: after a subscribe or an existing subscription. */
export const isOn = (branch: AlertsBranch) => branch === 'on'

type EnableStatus = EnableOutcome['status']

/** What an enable attempt changes on screen. `unsupported` and `error` change nothing: the browser view decides. */
export function afterEnable(status: EnableStatus): AfterEnable {
  switch (status) {
    case 'enabled':
      return 'enabled'
    case 'denied':
    case 'blocked':
      return 'denied'
    case 'dismissed':
      return 'dismissed'
    case 'device_limit':
      return 'device_limit'
    case 'unsupported':
    case 'error':
      return null
  }
}

/** Said in the polite live region when an enable attempt ends. */
export function enableAnnouncement(status: EnableStatus): string {
  switch (status) {
    case 'enabled':
      return 'Alerts are on for this device.'
    case 'denied':
    case 'blocked':
      return 'Alerts were not allowed. You can change this later in Settings.'
    case 'dismissed':
      return 'The browser prompt closed without an answer.'
    case 'device_limit':
      return 'This device could not be added: you have the most devices we allow.'
    case 'unsupported':
      return 'This browser cannot show alerts.'
    case 'error':
      return 'We could not turn alerts on. Please try again.'
  }
}
