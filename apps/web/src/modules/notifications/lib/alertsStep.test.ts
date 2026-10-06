import { describe, expect, it } from 'vitest'

import {
  afterEnable,
  type AlertsBranch,
  alertsBranch,
  type AlertsResult,
  enableAnnouncement,
  resultFor,
  shouldRecordPrePrompt,
  stateFor,
} from './alertsStep'
import type { PermissionView } from './permissionView'

const view = (kind: PermissionView['kind']): PermissionView =>
  (kind === 'in_app_browser' ? { kind, app: 'WhatsApp' } : { kind }) as PermissionView

describe('alertsBranch: one screen for every row of PRD 5.1', () => {
  const rows: Array<[PermissionView['kind'], AlertsBranch]> = [
    ['checking', 'checking'],
    ['in_app_browser', 'in_app_browser'],
    ['ios_needs_install', 'install'],
    ['unsupported', 'unsupported'],
    ['not_configured', 'not_configured'],
    ['blocked', 'blocked'],
    ['ready', 'pre_prompt'],
    ['granted_no_device', 'finish_setup'],
    ['active', 'on'],
  ]
  it.each(rows)('browser view %s shows %s', (kind, expected) => {
    expect(alertsBranch(view(kind), null)).toBe(expected)
  })

  it('what the student just did wins over a browser that has not caught up', () => {
    expect(alertsBranch(view('ready'), 'enabled')).toBe('on')
    expect(alertsBranch(view('blocked'), 'denied')).toBe('denied')
    expect(alertsBranch(view('ready'), 'dismissed')).toBe('dismissed')
    expect(alertsBranch(view('ready'), 'device_limit')).toBe('device_limit')
  })
})

describe('resultFor: how each branch ends', () => {
  const rows: Array<[AlertsBranch, AlertsResult | null]> = [
    ['pre_prompt', 'dismissed'],
    ['finish_setup', 'dismissed'],
    ['in_app_browser', 'dismissed'],
    ['dismissed', 'dismissed'],
    ['install', 'skipped_install'],
    ['unsupported', 'unsupported'],
    ['blocked', 'blocked'],
    ['denied', 'denied'],
    ['on', 'granted'],
    ['device_limit', 'granted'],
    ['checking', null],
    ['not_configured', null],
  ]
  it.each(rows)('%s finishes with %s', (branch, expected) => {
    expect(resultFor(branch)).toBe(expected)
  })

  it('stores an arrival block as denied and every other result as itself', () => {
    expect(stateFor('blocked')).toBe('denied')
    for (const result of ['granted', 'denied', 'dismissed', 'skipped_install', 'unsupported'] as const) {
      expect(stateFor(result)).toBe(result)
    }
  })
})

describe('shouldRecordPrePrompt', () => {
  it('counts the pre-prompt as an ask once, and only before the server has one', () => {
    expect(shouldRecordPrePrompt('pre_prompt', 'not_asked')).toBe(true)
    expect(shouldRecordPrePrompt('pre_prompt', 'pre_prompt_shown')).toBe(false)
    expect(shouldRecordPrePrompt('pre_prompt', 'dismissed')).toBe(false)
    expect(shouldRecordPrePrompt('pre_prompt', undefined)).toBe(false)
    expect(shouldRecordPrePrompt('blocked', 'not_asked')).toBe(false)
  })
})

describe('enable outcomes', () => {
  it('maps every outcome to a screen change and a spoken line', () => {
    expect(afterEnable('enabled')).toBe('enabled')
    expect(afterEnable('denied')).toBe('denied')
    expect(afterEnable('blocked')).toBe('denied')
    expect(afterEnable('dismissed')).toBe('dismissed')
    expect(afterEnable('device_limit')).toBe('device_limit')
    expect(afterEnable('unsupported')).toBeNull()
    expect(afterEnable('error')).toBeNull()
    for (const status of [
      'enabled',
      'denied',
      'blocked',
      'dismissed',
      'device_limit',
      'unsupported',
      'error',
    ] as const) {
      expect(enableAnnouncement(status).length).toBeGreaterThan(10)
    }
  })
})
