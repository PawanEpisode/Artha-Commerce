import { describe, expect, it } from 'vitest'

import { describeTransition } from './alerts'
import type { FocusTimer } from './types'

const t = (patch: Partial<FocusTimer>): FocusTimer =>
  ({
    phase: 'focus',
    status: 'running',
    round_number: 1,
    rounds_before_long: 4,
    client_id: 'a',
    ...patch,
  }) as FocusTimer

describe('describeTransition', () => {
  it('says nothing on first load or while the same phase runs', () => {
    expect(describeTransition(null, t({}))).toBeNull()
    expect(describeTransition(t({}), t({}))).toBeNull()
  })

  it('announces the end of a focus round and what comes next', () => {
    expect(describeTransition(t({}), t({ phase: 'short_break', client_id: 'b' }))?.body).toMatch(/short break/)
    expect(describeTransition(t({}), t({ phase: 'long_break', client_id: 'b' }))?.body).toMatch(/long break/)
    expect(describeTransition(t({}), null)?.title).toBe('Focus round done')
  })

  it('announces the end of a break', () => {
    const next = t({ round_number: 2, client_id: 'c' })
    expect(describeTransition(t({ phase: 'short_break' }), next)?.body).toBe('Round 2 of 4 has started.')
    expect(describeTransition(t({ phase: 'short_break' }), null)?.body).toBe('Ready for the next round?')
  })

  it('asks the student when a round ended while they were away', () => {
    expect(describeTransition(t({}), t({ status: 'away' }))?.title).toBe('Did you finish the round?')
    expect(describeTransition(t({ status: 'away' }), t({ status: 'away' }))).toBeNull()
  })
})
