/**
 * Study targets as pure functions, mirrored from apps/api/modules/coverage/domain/targets.py and checked against the
 * same fixtures (`rules_cases.json`). The preset table itself comes from the API; `DEFAULT_PRESETS` is the same table
 * for the first paint and for tests.
 */
import type { PresetKey, TargetPreset, Targets, TargetsPreset } from './types'

export type Direction = 'same' | 'raised' | 'lowered' | 'mixed'
export type TargetField = keyof Targets

export const TARGET_MIN = 0
export const TARGET_MAX = 10

export const DEFAULT_TARGETS: Targets = { practice_sets: 1, revisions: 2, mocks: 1 }

export const DEFAULT_PRESETS: ReadonlyArray<TargetPreset> = [
  { key: 'light', label: 'Light', practice_sets: 1, revisions: 1, mocks: 1 },
  { key: 'standard', label: 'Standard', practice_sets: 2, revisions: 2, mocks: 2 },
  { key: 'intense', label: 'Intense', practice_sets: 3, revisions: 3, mocks: 3 },
]

/** Field order and wording of the three steppers: one table, so the form, the summary and the dialog agree. */
export const TARGET_FIELDS: ReadonlyArray<{ key: TargetField; label: string; hint: string }> = [
  { key: 'practice_sets', label: 'Practice sets', hint: 'per chapter' },
  { key: 'revisions', label: 'Revision rounds', hint: 'per chapter' },
  { key: 'mocks', label: 'Mock tests', hint: 'per chapter' },
]

export const targetsEqual = (a: Targets, b: Targets) =>
  a.practice_sets === b.practice_sets && a.revisions === b.revisions && a.mocks === b.mocks

const asTuple = (t: Targets) => [t.practice_sets, t.revisions, t.mocks] as const

export const targetsValid = (t: Targets, min = TARGET_MIN, max = TARGET_MAX) =>
  asTuple(t).every((n) => Number.isInteger(n) && n >= min && n <= max)

/** The preset these numbers equal, else `custom`. */
export function presetFor(t: Targets, presets: ReadonlyArray<TargetPreset> = DEFAULT_PRESETS): TargetsPreset {
  return presets.find((p) => targetsEqual(p, t))?.key ?? 'custom'
}

export function directionOf(old: Targets, next: Targets): Direction {
  const pairs = asTuple(old).map((o, i) => [o, asTuple(next)[i] as number] as const)
  const up = pairs.some(([o, n]) => n > o)
  const down = pairs.some(([o, n]) => n < o)
  if (up && down) return 'mixed'
  if (up) return 'raised'
  return down ? 'lowered' : 'same'
}

/** Raising a target can lower percentages, so those saves are previewed first. */
export const needsImpactCheck = (old: Targets, next: Targets) => {
  const d = directionOf(old, next)
  return d === 'raised' || d === 'mixed'
}

export const targetsOfPreset = (preset: TargetPreset): Targets => ({
  practice_sets: preset.practice_sets,
  revisions: preset.revisions,
  mocks: preset.mocks,
})

export const presetLabel = (key: TargetsPreset, presets: ReadonlyArray<TargetPreset> = DEFAULT_PRESETS) =>
  key === 'custom' ? 'Custom' : (presets.find((p) => p.key === (key as PresetKey))?.label ?? 'Custom')

/** "2 · 2 · 2": the compact line shown under a preset and in summaries. */
export const targetsLine = (t: Targets) => asTuple(t).join(' · ')

/** Plain sentence for the impact dialog. */
export function impactSentence(chaptersDropping: number): string {
  return chaptersDropping === 1
    ? '1 chapter will show a lower percentage.'
    : `${chaptersDropping} chapters will show a lower percentage.`
}
