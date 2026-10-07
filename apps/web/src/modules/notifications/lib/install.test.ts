import { describe, expect, it } from 'vitest'

import {
  INSTALL_AFTER_ROUNDS,
  INSTALL_COOLDOWN_DAYS,
  installKind,
  installOfferDue,
  type InstallOfferFacts,
} from './install'

const env = (patch: Record<string, unknown> = {}) => ({
  platform: 'windows' as const,
  browser: 'chrome' as const,
  displayMode: 'browser' as const,
  inAppBrowser: null as string | null,
  ...patch,
})

describe('installKind', () => {
  it('is a one-click prompt where Chrome or Edge handed over the install event', () => {
    expect(installKind(env(), true)).toBe('prompt')
    expect(installKind(env({ browser: 'edge' }), true)).toBe('prompt')
    expect(installKind(env({ platform: 'android' }), true)).toBe('prompt')
  })

  it('shows the Home Screen steps on iPhone and iPad Safari, whatever else is true', () => {
    expect(installKind(env({ platform: 'ios', browser: 'safari' }), false)).toBe('ios_steps')
    expect(installKind(env({ platform: 'ios', browser: 'safari' }), true)).toBe('ios_steps')
  })

  it('shows File, then Add to Dock in Safari on a Mac', () => {
    expect(installKind(env({ platform: 'macos', browser: 'safari' }), false)).toBe('mac_safari')
  })

  it('offers nothing where the browser has no install: Firefox, or Chrome before the event fired', () => {
    expect(installKind(env({ browser: 'firefox' }), false)).toBeNull()
    expect(installKind(env(), false)).toBeNull()
    expect(installKind(env({ platform: 'ios', browser: 'chrome' }), false)).toBeNull()
  })

  it('never offers it inside the installed app or another app’s browser', () => {
    expect(installKind(env({ displayMode: 'standalone' }), true)).toBeNull()
    expect(installKind(env({ platform: 'ios', browser: 'safari', displayMode: 'standalone' }), false)).toBeNull()
    expect(installKind(env({ inAppBrowser: 'WhatsApp' }), true)).toBeNull()
  })
})

describe('installOfferDue', () => {
  const DAY = 24 * 60 * 60 * 1000
  const now = Date.parse('2026-10-07T10:00:00Z')
  const due: InstallOfferFacts = {
    flagOn: true,
    kind: 'prompt',
    deviceRounds: INSTALL_AFTER_ROUNDS,
    roundsFinished: 1,
    lastOfferedAt: null,
    now,
  }

  it('is due after the second finished round on this device, just after a round ended', () => {
    expect(installOfferDue(due)).toBe(true)
  })

  it('waits for the second round', () => {
    expect(installOfferDue({ ...due, deviceRounds: INSTALL_AFTER_ROUNDS - 1 })).toBe(false)
  })

  it('waits for a round to end during this visit', () => {
    expect(installOfferDue({ ...due, roundsFinished: 0 })).toBe(false)
  })

  it('is not due with the flag off or when this browser cannot install', () => {
    expect(installOfferDue({ ...due, flagOn: false })).toBe(false)
    expect(installOfferDue({ ...due, kind: null })).toBe(false)
  })

  it('is shown at most once every 30 days', () => {
    expect(INSTALL_COOLDOWN_DAYS).toBe(30)
    expect(installOfferDue({ ...due, lastOfferedAt: now - 29 * DAY })).toBe(false)
    expect(installOfferDue({ ...due, lastOfferedAt: now - 30 * DAY })).toBe(true)
  })
})
