import type { notificationAnalytics } from './analytics'
import { isDeviceLimit, postPermissionState, registerDevice } from './api'
import type { Environment } from './platform'
import { enablePush, type PushBrowser } from './push'
import { buildRegistration } from './register'
import type { DeviceRegistration, PermissionSource, PermissionState } from './schemas'

export type EnableOutcome =
  | { status: 'enabled'; deviceId: string }
  | { status: 'blocked' | 'denied' | 'dismissed' | 'unsupported' | 'device_limit' }
  | { status: 'error'; reason: 'bad_key' | 'subscribe_failed' | 'register_failed' }

export interface EnableDeps {
  browser: PushBrowser
  environment: Environment
  vapidPublicKey: string
  source: PermissionSource
  analytics: Pick<typeof notificationAnalytics, 'permissionPrompted' | 'permissionResult'>
  api?: {
    registerDevice: (body: DeviceRegistration) => Promise<string>
    postPermissionState: (state: PermissionState, source: PermissionSource) => Promise<unknown>
  }
}

/**
 * The whole "turn on alerts on this device" flow, with every outside effect passed in: ask the browser (once, never
 * when blocked), subscribe, record the decision, register the device. The result is data; wording and toasts belong to
 * the caller. Recording the decision is best effort: a failure there never undoes a working subscription.
 */
export async function enableAlerts(deps: EnableDeps): Promise<EnableOutcome> {
  const api = deps.api ?? { registerDevice, postPermissionState }
  const record = (state: PermissionState) => api.postPermissionState(state, deps.source).catch(() => undefined)

  const willPrompt = deps.browser.permission() === 'default'
  if (willPrompt) deps.analytics.permissionPrompted(deps.source)

  const result = await enablePush(deps.browser, deps.vapidPublicKey)

  if (willPrompt) {
    // An error after the prompt still means the student said yes.
    const answer = result.status === 'denied' ? 'denied' : result.status === 'dismissed' ? 'dismissed' : 'granted'
    deps.analytics.permissionResult(answer, deps.source)
    await record(answer)
  } else if (result.status === 'denied') {
    await record('denied')
  }

  switch (result.status) {
    case 'blocked':
    case 'denied':
    case 'dismissed':
    case 'unsupported':
      return { status: result.status }
    case 'error':
      return { status: 'error', reason: result.reason }
    case 'subscribed':
      break
  }

  if (!willPrompt) await record('granted')
  try {
    const deviceId = await api.registerDevice(buildRegistration(result.subscription, deps.environment))
    return { status: 'enabled', deviceId }
  } catch (error) {
    if (isDeviceLimit(error)) {
      // Never registered, so nothing would ever be sent to it: drop the browser side too.
      await result.subscription.unsubscribe().catch(() => false)
      return { status: 'device_limit' }
    }
    return { status: 'error', reason: 'register_failed' }
  }
}
