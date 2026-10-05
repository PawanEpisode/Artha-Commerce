import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  DEFAULT_PRESETS,
  directionOf,
  impactSentence,
  needsImpactCheck,
  presetFor,
  targetsEqual,
  targetsLine,
  targetsValid,
} from './targets'
import type { Targets } from './types'

type Triple = [number, number, number]
const t = ([practice_sets, revisions, mocks]: Triple): Targets => ({ practice_sets, revisions, mocks })

const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/coverage/tests/fixtures/rules_cases.json', import.meta.url)),
    'utf8',
  ),
) as {
  preset_for: Array<{ name: string; targets: Triple; expected: string }>
  direction_of: Array<{ name: string; old: Triple; new: Triple; expected: string }>
}

describe('shared target fixtures', () => {
  it.each(fixtures.preset_for)('preset_for: $name', ({ targets, expected }) => {
    expect(presetFor(t(targets))).toBe(expected)
  })
  it.each(fixtures.direction_of)('direction_of: $name', ({ old, new: next, expected }) => {
    expect(directionOf(t(old), t(next))).toBe(expected)
  })
})

describe('targets helpers', () => {
  it('knows the three presets', () => {
    expect(DEFAULT_PRESETS.map((p) => p.key)).toEqual(['light', 'standard', 'intense'])
  })
  it('compares and validates', () => {
    expect(targetsEqual(t([1, 2, 3]), t([1, 2, 3]))).toBe(true)
    expect(targetsEqual(t([1, 2, 3]), t([1, 2, 4]))).toBe(false)
    expect(targetsValid(t([0, 10, 5]))).toBe(true)
    expect(targetsValid(t([0, 11, 5]))).toBe(false)
    expect(targetsValid(t([0, 1.5, 5]))).toBe(false)
  })
  it('previews only when a target goes up', () => {
    expect(needsImpactCheck(t([2, 2, 2]), t([1, 1, 1]))).toBe(false)
    expect(needsImpactCheck(t([1, 1, 1]), t([1, 2, 1]))).toBe(true)
    expect(needsImpactCheck(t([3, 1, 1]), t([1, 2, 1]))).toBe(true)
    expect(needsImpactCheck(t([1, 1, 1]), t([1, 1, 1]))).toBe(false)
  })
  it('formats', () => {
    expect(targetsLine(t([1, 2, 3]))).toBe('1 · 2 · 3')
    expect(impactSentence(1)).toBe('1 chapter will show a lower percentage.')
    expect(impactSentence(4)).toBe('4 chapters will show a lower percentage.')
  })
})
