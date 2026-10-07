import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  effectiveLink,
  type OutlineNode,
  type PageRange,
  type RangeProblem,
  rangesFromOutline,
  type SuggestedRange,
  validateRanges,
} from './chapter-inheritance'

// The same fixtures the Python tests use: the two implementations must agree on every case.
const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/notes/tests/fixtures/inheritance_cases.json', import.meta.url)),
    'utf8',
  ),
) as {
  effective: {
    name: string
    page: number
    explicit: string | null
    ranges: PageRange[]
    default: string | null
    expected: unknown
  }[]
  validate: { name: string; ranges: PageRange[]; expected: RangeProblem | null }[]
  outline: { name: string; outline: OutlineNode[]; page_count: number; expected: SuggestedRange[] }[]
}

describe('effectiveLink', () => {
  it.each(fixtures.effective.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    expect(effectiveLink(c.page, c.explicit, c.ranges, c.default)).toEqual(c.expected)
  })
})

describe('validateRanges', () => {
  it.each(fixtures.validate.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    expect(validateRanges(c.ranges)).toEqual(c.expected)
  })
})

describe('rangesFromOutline', () => {
  it.each(fixtures.outline.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    expect(rangesFromOutline(c.outline, c.page_count)).toEqual(c.expected)
    expect(validateRanges(rangesFromOutline(c.outline, c.page_count))).toBeNull()
  })
})
