import { describe, expect, it } from 'vitest'

import { derivePermissionView, type PermissionFacts, unblockSteps } from './permissionView'
import type { Environment } from './platform'

const env = (patch: Partial<Environment> = {}): Environment => ({
  platform: 'windows',
  browser: 'chrome',
  displayMode: 'browser',
  inAppBrowser: null,
  support: 'supported',
  label: 'Chrome on Windows',
  ...patch,
})
const facts = (patch: Partial<PermissionFacts> = {}): PermissionFacts => ({
  environment: env(),
  permission: 'default',
  subscribed: false,
  vapidConfigured: true,
  ...patch,
})
const kind = (patch?: Partial<PermissionFacts>) => derivePermissionView(facts(patch)).kind

describe('derivePermissionView', () => {
  it('waits until the browser has been asked', () => {
    expect(kind({ environment: null })).toBe('checking')
    expect(kind({ permission: 'granted', subscribed: null })).toBe('checking')
  })

  it('puts the environment first: in-app browser, iOS install, unsupported', () => {
    const inApp = derivePermissionView(
      facts({ environment: env({ support: 'in_app_browser', inAppBrowser: 'Instagram' }), permission: 'denied' }),
    )
    expect(inApp).toEqual({ kind: 'in_app_browser', app: 'Instagram' })
    expect(
      kind({ environment: env({ support: 'ios_needs_install', platform: 'ios' }), permission: 'unsupported' }),
    ).toBe('ios_needs_install')
    expect(kind({ environment: env({ support: 'unsupported' }) })).toBe('unsupported')
    expect(kind({ permission: 'unsupported' })).toBe('unsupported')
  })

  it('says so when the build has no VAPID key', () => {
    expect(kind({ vapidConfigured: false })).toBe('not_configured')
  })

  it('tells blocked from not yet asked', () => {
    expect(kind({ permission: 'denied' })).toBe('blocked')
    expect(kind({ permission: 'denied', subscribed: true })).toBe('blocked')
    expect(kind({ permission: 'default' })).toBe('ready')
  })

  it('tells registered from granted-but-not-registered', () => {
    expect(kind({ permission: 'granted', subscribed: true })).toBe('active')
    expect(kind({ permission: 'granted', subscribed: false })).toBe('granted_no_device')
  })
})

describe('unblockSteps', () => {
  it('speaks the language of the browser and device', () => {
    expect(unblockSteps('safari', 'ios')).toMatch(/Settings.*Notifications/)
    expect(unblockSteps('safari', 'macos')).toMatch(/Safari menu/)
    expect(unblockSteps('firefox', 'windows')).toMatch(/permissions icon/)
    expect(unblockSteps('chrome', 'android')).toMatch(/Tap the lock icon/)
    expect(unblockSteps('chrome', 'windows')).toMatch(/lock icon/)
  })
})
