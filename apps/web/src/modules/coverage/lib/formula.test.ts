import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  type ChapterInputs,
  computeComponents,
  DEFAULT_WEIGHTS,
  deriveStatus,
  nextRevisionDue,
  revisionDaysValid,
  rollup,
  roundHalfUp,
  weightsValid,
} from './formula'

interface Case {
  name: string
  inputs: Record<string, number>
  expected: Record<string, number>
}

// The same fixtures the Python tests use: the two implementations must agree on every case.
const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/coverage/tests/fixtures/formula_cases.json', import.meta.url)),
    'utf8',
  ),
) as { weights: typeof DEFAULT_WEIGHTS; cases: Case[] }

const toInputs = (i: Record<string, number>): ChapterInputs => ({
  topicsTotal: i.topics_total,
  topicsDone: i.topics_done,
  practiceCount: i.practice_count,
  revisionCount: i.revision_count,
  mockCount: i.mock_count,
  targetPracticeSets: i.target_practice_sets,
  targetRevisions: i.target_revisions,
  targetMocks: i.target_mocks,
})

describe('computeComponents (shared fixtures)', () => {
  it('uses the default weights from the fixtures', () => expect(fixtures.weights).toEqual(DEFAULT_WEIGHTS))
  it.each(fixtures.cases)('$name', ({ inputs, expected }) => {
    expect(computeComponents(toInputs(inputs), fixtures.weights)).toEqual(expected)
  })
})

describe('deriveStatus', () => {
  const base = { readPct: 0, coveragePct: 0, practiceCount: 0, revisionCount: 0, anyActivity: false }
  it.each([
    [{}, 'not_started'],
    [{ anyActivity: true }, 'reading'],
    [{ readPct: 40, coveragePct: 16, anyActivity: true }, 'reading'],
    [{ readPct: 100, coveragePct: 40, anyActivity: true }, 'reading'],
    [{ readPct: 100, coveragePct: 70, practiceCount: 1, anyActivity: true }, 'practised'],
    [{ readPct: 100, coveragePct: 70, practiceCount: 1, revisionCount: 1, anyActivity: true }, 'revised_once'],
    [{ readPct: 100, coveragePct: 80, practiceCount: 1, revisionCount: 2, anyActivity: true }, 'revised_twice_plus'],
    [{ readPct: 100, coveragePct: 85, practiceCount: 1, revisionCount: 2, anyActivity: true }, 'exam_ready'],
    [{ readPct: 100, coveragePct: 95, practiceCount: 1, revisionCount: 1, anyActivity: true }, 'revised_once'],
  ])('%j gives %s', (over, expected) => {
    expect(deriveStatus({ ...base, ...over })).toBe(expected)
  })
})

describe('rollup', () => {
  it('excludes excluded chapters and weights by marks', () => {
    const r = rollup([
      { coveragePct: 100, weight: 15, isExcluded: false, status: 'exam_ready' },
      { coveragePct: 0, weight: 5, isExcluded: false, status: 'not_started' },
      { coveragePct: 50, weight: 100, isExcluded: true, status: 'reading' },
    ])
    expect(r).toEqual({ pctSimple: 50, pctWeighted: 75, chaptersTotal: 2, chaptersDone: 1 })
  })
  it('is zero when empty or everything is excluded', () => {
    expect(rollup([]).chaptersTotal).toBe(0)
    expect(rollup([{ coveragePct: 10, weight: 1, isExcluded: true, status: 'reading' }]).chaptersTotal).toBe(0)
  })
})

describe('nextRevisionDue', () => {
  const days = [3, 7, 21, 45]
  it('follows the schedule and repeats the last gap', () => {
    expect(nextRevisionDue('2026-10-04', 1, days)).toBe('2026-10-07')
    expect(nextRevisionDue('2026-10-04', 2, days)).toBe('2026-10-11')
    expect(nextRevisionDue('2026-10-04', 4, days)).toBe('2026-11-18')
    expect(nextRevisionDue('2026-10-04', 9, days)).toBe('2026-11-18')
    expect(nextRevisionDue('2026-10-04', 0, days)).toBeNull()
  })
})

describe('validators and rounding', () => {
  it('rounds half up', () => {
    expect(roundHalfUp(12.5)).toBe(13)
    expect(roundHalfUp(2.5)).toBe(3)
  })
  it('validates weights', () => {
    expect(weightsValid({ read: 40, practice: 30, revise: 20, mock: 10 })).toBe(true)
    expect(weightsValid({ read: 40, practice: 30, revise: 20, mock: 20 })).toBe(false)
    expect(weightsValid({ read: -10, practice: 60, revise: 30, mock: 20 })).toBe(false)
  })
  it('validates revision days', () => {
    expect(revisionDaysValid([3, 7])).toBe(true)
    expect(revisionDaysValid([])).toBe(false)
    expect(revisionDaysValid([0])).toBe(false)
    expect(revisionDaysValid(Array(9).fill(1))).toBe(false)
  })
})
