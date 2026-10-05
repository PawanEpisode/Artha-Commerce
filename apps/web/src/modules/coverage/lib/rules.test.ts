import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  activityProgress,
  canLog,
  chapterActivities,
  confidenceAllowed,
  confidenceHint,
  everythingLogged,
  formatProgress,
  logBlockedReason,
} from './rules'

interface Fixtures {
  can_log: Array<{ name: string; count: number; add: number; target: number; expected: string }>
  confidence_allowed: Array<{ coverage_pct: number; expected: boolean }>
  activity_progress: Array<{
    count: number
    target: number
    expected: { done: number; target: number; logged: number; can_log: boolean }
  }>
}

// The Python tests read the same file: both implementations must agree on every case.
const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/coverage/tests/fixtures/rules_cases.json', import.meta.url)),
    'utf8',
  ),
) as Fixtures

describe('shared rule fixtures', () => {
  it.each(fixtures.can_log)('can_log: $name', ({ count, add, target, expected }) => {
    expect(canLog({ count, add, target })).toBe(expected)
  })

  it.each(fixtures.confidence_allowed)('confidence at $coverage_pct%', ({ coverage_pct, expected }) => {
    expect(confidenceAllowed(coverage_pct)).toBe(expected)
  })

  it.each(fixtures.activity_progress)('activity $count of $target', ({ count, target, expected }) => {
    const got = activityProgress(count, target)
    expect({ done: got.done, target: got.target, logged: got.logged, can_log: got.canLog }).toEqual(expected)
  })
})

const chapter = (over: Partial<Parameters<typeof chapterActivities>[0]> = {}) => ({
  practice_count: 0,
  revision_count: 0,
  mock_count: 0,
  targets: { practice: 1, revisions: 2, mocks: 1 },
  ...over,
})

describe('chapterActivities', () => {
  it('never shows more than the target as done, even for legacy rows (2 mocks, target 1)', () => {
    const a = chapterActivities(chapter({ mock_count: 2 }))
    expect(a.mocks).toMatchObject({ done: 1, target: 1, logged: 2, canLog: false })
    expect(formatProgress(a.mocks, 'tests')).toBe('1 of 1 tests (2 logged)')
  })

  it('shows a plain "N of M" when nothing is above the target', () => {
    const a = chapterActivities(chapter({ revision_count: 1 }))
    expect(formatProgress(a.revisions, 'rounds')).toBe('1 of 2 rounds')
  })
})

describe('log blocking copy', () => {
  it('explains an activity at target', () => {
    const a = chapterActivities(chapter({ mock_count: 1 }))
    expect(logBlockedReason('mocks', a.mocks)).toBe('You have logged all 1 mock tests for this chapter.')
    expect(logBlockedReason('practice', a.practice)).toBeNull()
  })

  it('says an untracked activity is not part of the plan', () => {
    const a = chapterActivities(chapter({ targets: { practice: 0, revisions: 2, mocks: 1 } }))
    expect(logBlockedReason('practice', a.practice)).toBe('Practice sets are not part of your plan.')
  })

  it('is done only when every tracked activity is complete', () => {
    expect(everythingLogged(chapterActivities(chapter({ practice_count: 1, revision_count: 2 })))).toBe(false)
    expect(everythingLogged(chapterActivities(chapter({ practice_count: 1, revision_count: 2, mock_count: 1 })))).toBe(
      true,
    )
    const untracked = chapterActivities(chapter({ targets: { practice: 0, revisions: 0, mocks: 0 } }))
    expect(everythingLogged(untracked)).toBe(false) // nothing to finish, so no "done" celebration
  })
})

describe('confidenceHint', () => {
  it('names the threshold and the current percent', () => {
    expect(confidenceHint(38)).toBe('Available once this chapter is 50% complete. It is at 38% now.')
  })
})
