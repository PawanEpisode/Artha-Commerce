import { track } from '~/modules/observability'

import type { Channel, ClickInfo, PermissionSource } from './schemas'

/** Web events of PRD section 10 (`noun_verb`). Properties never carry endpoints, keys, ids or notification text. */
export const NOTIFICATION_EVENTS = {
  permissionPrompted: 'push_permission_prompted',
  permissionResult: 'push_permission_result',
  testRequested: 'push_test_requested',
  deviceRemoved: 'push_device_removed',
  prefChanged: 'notification_pref_changed',
  pushClicked: 'push_clicked',
} as const

export type PermissionResult = 'granted' | 'denied' | 'dismissed'

export const notificationAnalytics = {
  /** The browser prompt is about to show. */
  permissionPrompted: (source: PermissionSource) => track(NOTIFICATION_EVENTS.permissionPrompted, { source }),
  permissionResult: (result: PermissionResult, source: PermissionSource) =>
    track(NOTIFICATION_EVENTS.permissionResult, { result, source }),
  testRequested: (platform: string) => track(NOTIFICATION_EVENTS.testRequested, { platform }),
  deviceRemoved: (platform: string) => track(NOTIFICATION_EVENTS.deviceRemoved, { platform }),
  prefChanged: (change: { category: string; channel: Channel; enabled: boolean }) =>
    track(NOTIFICATION_EVENTS.prefChanged, {
      category: change.category,
      channel: change.channel,
      enabled: change.enabled,
    }),
  /** Only the fields the API returned are sent; a missing one is left out rather than guessed. */
  pushClicked: (info: ClickInfo) =>
    track(NOTIFICATION_EVENTS.pushClicked, {
      ...(info.category === undefined ? {} : { category: info.category }),
      ...(info.seconds_since_sent === undefined ? {} : { seconds_since_sent: info.seconds_since_sent }),
    }),
}
