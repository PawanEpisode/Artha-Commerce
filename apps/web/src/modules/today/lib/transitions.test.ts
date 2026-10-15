import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

import { incomingWins, transition } from './transitions'
import type { TaskOrigin, TaskState } from './types'

interface Case {
  name: string
  state: TaskState
  action: string
  origin?: TaskOrigin
  prev_state?: TaskState | null
  within_undo?: boolean
  within_grace?: boolean
  same_day?: boolean
  to?: TaskState
  error?: string
  allowed?: string[]
}
interface Conflict {
  name: string
  state: TaskState
  action: string
  current_ts: number
  client_ts: number
  wins: boolean
}

// The API's shared fixture is the source of truth: if it moves, this test must fail loudly, not skip.
const fixture = JSON.parse(
  readFileSync(
    new URL('../../../../../api/modules/today/tests/fixtures/state_transitions.json', import.meta.url),
    'utf8',
  ),
) as { transitions: Case[]; conflicts: Conflict[] }

describe('transitions mirror: shared state machine cases', () => {
  it('loads the shared cases', () => {
    expect(fixture.transitions.length).toBeGreaterThan(30)
    expect(fixture.conflicts.length).toBeGreaterThan(5)
  })

  it.each(fixture.transitions.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const got = transition(c.state, c.action, {
      origin: c.origin,
      prevState: c.prev_state,
      withinUndo: c.within_undo,
      withinGrace: c.within_grace,
      sameDay: c.same_day,
    })
    if (c.error) {
      expect(got).toMatchObject({ error: c.error })
      if (c.allowed) expect([...(got as { allowed: string[] }).allowed].sort()).toEqual([...c.allowed].sort())
    } else {
      expect(got).toEqual({ to: c.to })
    }
  })

  it.each(fixture.conflicts.map((c) => [c.name, c] as const))('conflict: %s', (_name, c) => {
    expect(incomingWins(c.state, c.action, c.current_ts, c.client_ts)).toBe(c.wins)
  })
})
