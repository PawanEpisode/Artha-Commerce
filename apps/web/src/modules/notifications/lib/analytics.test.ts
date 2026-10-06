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
    })
    for (const name of Object.values(NOTIFICATION_EVENTS)) expect(name).toMatch(/^[a-z]+(_[a-z]+)+$/)
  })

  it('sends the prompt and its result with the source', () => {
    notificationAnalytics.permissionPrompted('settings')
    notificationAnalytics.permissionResult('granted', 'settings')
    expect(track).toHaveBeenNthCalledWith(1, 'push_permission_prompted', { source: 'settings' })
    expect(track).toHaveBeenNthCalledWith(2, 'push_permission_result', { result: 'granted', source: 'settings' })
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
})
