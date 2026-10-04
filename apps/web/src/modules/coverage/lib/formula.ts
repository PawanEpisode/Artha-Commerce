/**
 * The coverage maths, mirrored from apps/api/modules/coverage/domain/formula.py.
 * Used for optimistic UI and the "How is this calculated?" panel. The server is the source of truth: both sides
 * are tested against the same fixtures (apps/api/modules/coverage/tests/fixtures/formula_cases.json).
 */
import type { ChapterStatus } from './types'

export interface Weights {
  read: number
  practice: number
  revise: number
  mock: number
}

export const DEFAULT_WEIGHTS: Weights = { read: 40, practice: 30, revise: 20, mock: 10 }
export const DEFAULT_REVISION_DAYS = [3, 7, 21, 45]
export const EXAM_READY_COVERAGE = 85
export const EXAM_READY_REVISIONS = 2

/** Percentages round half up (Math.round differs for negatives; none occur here). */
export const roundHalfUp = (value: number) => Math.floor(value + 0.5)

export interface ChapterInputs {
  topicsTotal: number
  topicsDone: number
  practiceCount: number
  revisionCount: number
  mockCount: number
  targetPracticeSets: number
  targetRevisions: number
  targetMocks: number
}

export interface Components {
  read: number
  practice: number
  revise: number
  mock: number
  coverage: number
}

const component = (count: number, target: number) => roundHalfUp(100 * Math.min(1, count / target))

export function computeComponents(i: ChapterInputs, w: Weights = DEFAULT_WEIGHTS): Components {
  const total = Math.max(i.topicsTotal, 1)
  const read = roundHalfUp((100 * Math.min(i.topicsDone, total)) / total)
  const practice = i.targetPracticeSets ? component(i.practiceCount, i.targetPracticeSets) : 0
  const revise = i.targetRevisions ? component(i.revisionCount, i.targetRevisions) : 0
  const mock = i.targetMocks ? component(i.mockCount, i.targetMocks) : 0
  const parts: Array<[number, number]> = [
    [read, w.read],
    [practice, i.targetPracticeSets ? w.practice : 0],
    [revise, i.targetRevisions ? w.revise : 0],
    [mock, i.targetMocks ? w.mock : 0],
  ]
  const weightSum = parts.reduce((a, [, wt]) => a + wt, 0)
  const coverage = weightSum === 0 ? read : roundHalfUp(parts.reduce((a, [v, wt]) => a + v * wt, 0) / weightSum)
  return { read, practice, revise, mock, coverage: Math.min(coverage, 100) }
}

export function deriveStatus(p: {
  readPct: number
  coveragePct: number
  practiceCount: number
  revisionCount: number
  anyActivity: boolean
}): ChapterStatus {
  if (p.coveragePct >= EXAM_READY_COVERAGE && p.revisionCount >= EXAM_READY_REVISIONS) return 'exam_ready'
  if (p.revisionCount >= 2) return 'revised_twice_plus'
  if (p.revisionCount === 1) return 'revised_once'
  if (p.readPct === 100 && p.practiceCount >= 1) return 'practised'
  if (p.readPct > 0 || p.anyActivity) return 'reading'
  return 'not_started'
}

export interface RollupRow {
  coveragePct: number
  weight: number
  isExcluded: boolean
  status: ChapterStatus
}

export function rollup(rows: RollupRow[]) {
  const included = rows.filter((r) => !r.isExcluded)
  if (included.length === 0) return { pctSimple: 0, pctWeighted: 0, chaptersTotal: 0, chaptersDone: 0 }
  const simple = roundHalfUp(included.reduce((a, r) => a + r.coveragePct, 0) / included.length)
  const weightSum = included.reduce((a, r) => a + r.weight, 0)
  const weighted = weightSum
    ? roundHalfUp(included.reduce((a, r) => a + r.coveragePct * r.weight, 0) / weightSum)
    : simple
  const done = included.filter((r) => r.coveragePct >= 100 || r.status === 'exam_ready').length
  return { pctSimple: simple, pctWeighted: weighted, chaptersTotal: included.length, chaptersDone: done }
}

/** After the Nth revision the next is due `days[N - 1]` days later; the last gap repeats. Returns an ISO date. */
export function nextRevisionDue(occurredOn: string, revisionCount: number, days: number[]): string | null {
  if (revisionCount < 1 || days.length === 0) return null
  const gap = days[Math.min(revisionCount, days.length) - 1]
  const d = new Date(`${occurredOn}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + gap)
  return d.toISOString().slice(0, 10)
}

export const weightsTotal = (w: Weights) => w.read + w.practice + w.revise + w.mock

export function weightsValid(w: Weights): boolean {
  const values = [w.read, w.practice, w.revise, w.mock]
  return values.every((v) => Number.isInteger(v) && v >= 0 && v <= 100) && weightsTotal(w) === 100
}

export function revisionDaysValid(days: number[]): boolean {
  return days.length >= 1 && days.length <= 8 && days.every((d) => Number.isInteger(d) && d >= 1 && d <= 365)
}

/** Percent the student sees for a roll-up, honouring the simple/weighted toggle. */
export const pick = (r: { pct_simple: number; pct_weighted: number }, weighted: boolean) =>
  weighted ? r.pct_weighted : r.pct_simple
