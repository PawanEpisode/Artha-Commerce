import { BUILD_VERSION } from '~/lib/build-info'

import { registerDevice } from './api'
import type { Environment } from './platform'
import { currentSubscription, type PushBrowser, type PushSubscriptionLike, toDeviceKeys } from './push'
import type { DeviceRegistration } from './schemas'

/** The body of `POST devices/` for this browser. */
export function buildRegistration(subscription: PushSubscriptionLike, environment: Environment): DeviceRegistration {
  return {
    ...toDeviceKeys(subscription),
    platform: environment.platform,
    browser: environment.browser,
    display_mode: environment.displayMode,
    sw_version: BUILD_VERSION,
    label: environment.label,
  }
}

export interface SyncDeps {
  browser: PushBrowser
  environment: Environment
  register?: (body: DeviceRegistration) => Promise<string>
}

/**
 * Registers the subscription this browser already holds (no prompt, no new subscription). Returns the device id, or
 * null when there is nothing to register. Used after the student enables alerts, on a visit to settings, and when the
 * worker re-subscribed after the browser rotated the endpoint.
 */
export async function syncCurrentDevice(deps: SyncDeps): Promise<string | null> {
  if (deps.browser.permission() !== 'granted') return null
  const subscription = await currentSubscription(deps.browser)
  if (!subscription) return null
  return (deps.register ?? registerDevice)(buildRegistration(subscription, deps.environment))
}
