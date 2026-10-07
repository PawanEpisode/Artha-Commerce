import { describe, expect, it } from 'vitest'

import { digestCard, digestDoneMessage } from './digest'
import { digestSchema } from './schemas'

const state = (offer: boolean, enabled: boolean) => ({ offer, enabled, time: '10:00' })

describe('digestCard (W3.7)', () => {
  it('shows the offer on both pages when it is due', () => {
    expect(digestCard(state(true, false), 'inbox', true)).toBe('offer')
    expect(digestCard(state(true, false), 'settings', true)).toBe('offer')
  })

  it('shows the switch-back card only in settings once the digest is on', () => {
    expect(digestCard(state(false, true), 'settings', true)).toBe('status')
    expect(digestCard(state(false, true), 'inbox', true)).toBe('none')
    expect(digestCard(state(true, true), 'settings', true)).toBe('status')
  })

  it('shows nothing when there is nothing to say, no data yet, or the flag is off', () => {
    expect(digestCard(state(false, false), 'settings', true)).toBe('none')
    expect(digestCard(undefined, 'inbox', true)).toBe('none')
    expect(digestCard(state(true, false), 'inbox', false)).toBe('none')
  })
})

describe('digestSchema', () => {
  it('accepts the API answer and refuses a bad time', () => {
    expect(digestSchema.parse({ offer: true, enabled: false, time: '09:30' })).toEqual({
      offer: true,
      enabled: false,
      time: '09:30',
    })
    expect(() => digestSchema.parse({ offer: true, enabled: false, time: '9:30pm' })).toThrow()
  })
})

describe('digestDoneMessage', () => {
  it('names the time on accept and is calm otherwise', () => {
    expect(digestDoneMessage('accept', '10:00')).toContain('One digest a day at 10:00')
    expect(digestDoneMessage('stop', '10:00')).toMatch(/^Separate alerts are back on/)
    expect(digestDoneMessage('decline', '10:00')).toMatch(/^No change/)
  })
})
