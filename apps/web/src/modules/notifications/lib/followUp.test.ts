import { describe, expect, it } from 'vitest'

import { shouldAskFollowUp } from './followUp'
import type { PermissionView } from './permissionView'

const facts = (over: Partial<Parameters<typeof shouldAskFollowUp>[0]> = {}) => ({
  flagOn: true,
  due: true,
  view: { kind: 'ready' } as PermissionView,
  roundsFinished: 1,
  ...over,
})

describe('shouldAskFollowUp', () => {
  it('asks right after a finished round when the server says it is due and the browser can prompt', () => {
    expect(shouldAskFollowUp(facts())).toBe(true)
  })
  it('never asks before a round has finished on this visit', () => {
    expect(shouldAskFollowUp(facts({ roundsFinished: 0 }))).toBe(false)
  })
  it('never asks when the server has not said it is due (spacing and cap are its rules)', () => {
    expect(shouldAskFollowUp(facts({ due: false }))).toBe(false)
  })
  it('never asks while the flag is off', () => {
    expect(shouldAskFollowUp(facts({ flagOn: false }))).toBe(false)
  })
  it.each(['blocked', 'unsupported', 'ios_needs_install', 'in_app_browser', 'not_configured', 'active', 'checking'])(
    'never nags a device whose browser view is %s',
    (kind) => {
      expect(shouldAskFollowUp(facts({ view: { kind, app: 'x' } as PermissionView }))).toBe(false)
    },
  )
})
