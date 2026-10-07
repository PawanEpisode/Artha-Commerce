import { beforeEach, describe, expect, it, vi } from 'vitest'

const track = vi.hoisted(() => vi.fn())
vi.mock('~/modules/observability', () => ({ track }))

import { NOTIFICATION_EVENTS, notificationAnalytics } from './analytics'

beforeEach(() => track.mockClear())

describe('notification analytics (PRD 10)', () => {
  it('names every event noun_verb, as the PRD lists them', () => {
    expect(NOTIFICATION_EVENTS).toEqual({
      permissionPrompted: 'push_permission_prompted',
      permissionResult: 'push_permission_result',
      testRequested: 'push_test_requested',
      deviceRemoved: 'push_device_removed',
      prefChanged: 'notification_pref_changed',
      pushClicked: 'push_clicked',
      inboxOpened: 'inbox_opened',
      alertsStepViewed: 'alerts_step_viewed',
      alertsStepCompleted: 'alerts_step_completed',
      localAlertShown: 'local_alert_shown',
      digestOfferShown: 'digest_offer_shown',
      digestAnswered: 'digest_answered',
      pwaInstallResult: 'pwa_install_result',
    })
    for (const name of Object.values(NOTIFICATION_EVENTS)) expect(name).toMatch(/^[a-z]+(_[a-z]+)+$/)
  })

  it('sends the digest offer and its answer with the place only (W3.7)', () => {
    notificationAnalytics.digestOfferShown('inbox')
    notificationAnalytics.digestAnswered('accept', 'settings')
    expect(track).toHaveBeenNthCalledWith(1, 'digest_offer_shown', { place: 'inbox' })
    expect(track).toHaveBeenNthCalledWith(2, 'digest_answered', { answer: 'accept', place: 'settings' })
  })

  it('sends the prompt and its result with the source', () => {
    notificationAnalytics.permissionPrompted('settings')
    notificationAnalytics.permissionResult('granted', 'settings')
    expect(track).toHaveBeenNthCalledWith(1, 'push_permission_prompted', { source: 'settings' })
    expect(track).toHaveBeenNthCalledWith(2, 'push_permission_result', { result: 'granted', source: 'settings' })
  })

  it('sends the alerts step view and result with the platform and display mode only', () => {
    const where = { platform: 'ios', displayMode: 'standalone' } as const
    notificationAnalytics.alertsStepViewed('install', where)
    notificationAnalytics.alertsStepCompleted('skipped_install', where)
    expect(track).toHaveBeenNthCalledWith(1, 'alerts_step_viewed', {
      branch: 'install',
      platform: 'ios',
      display_mode: 'standalone',
    })
    expect(track).toHaveBeenNthCalledWith(2, 'alerts_step_completed', {
      result: 'skipped_install',
      platform: 'ios',
      display_mode: 'standalone',
    })
  })

  it('sends the platform with test and removal, and nothing else about the device', () => {
    notificationAnalytics.testRequested('android')
    notificationAnalytics.deviceRemoved('ios')
    expect(track).toHaveBeenNthCalledWith(1, 'push_test_requested', { platform: 'android' })
    expect(track).toHaveBeenNthCalledWith(2, 'push_device_removed', { platform: 'ios' })
  })

  it('sends category, channel and the new value for a switch', () => {
    notificationAnalytics.prefChanged({ category: 'timer', channel: 'push', enabled: false })
    expect(track).toHaveBeenCalledWith('notification_pref_changed', {
      category: 'timer',
      channel: 'push',
      enabled: false,
    })
  })

  it('sends only what the API returned for a click', () => {
    notificationAnalytics.pushClicked({ category: 'timer', seconds_since_sent: 42 })
    notificationAnalytics.pushClicked({})
    expect(track).toHaveBeenNthCalledWith(1, 'push_clicked', { category: 'timer', seconds_since_sent: 42 })
    expect(track).toHaveBeenNthCalledWith(2, 'push_clicked', {})
  })

  it('sends the category and the age of an opened inbox item, and no text or id', () => {
    notificationAnalytics.inboxOpened({ category: 'timer', seconds_since_sent: 90 })
    expect(track).toHaveBeenCalledWith('inbox_opened', { category: 'timer', seconds_since_sent: 90 })
  })
})
