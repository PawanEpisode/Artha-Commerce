import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { locateQuote, makeSelector, MIN_SCORE, normaliseForMatch } from './anchors'

// The same fixtures the Python tests use: the two implementations must agree on every case.
const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/notes/tests/fixtures/anchoring_cases.json', import.meta.url)),
    'utf8',
  ),
) as {
  normalise: { name: string; input: string; text: string; starts: number[]; ends: number[] }[]
  selector: { name: string; page_text: string; start: number; end: number; expected: Record<string, unknown> }[]
  locate: {
    name: string
    page_text: string
    quote_exact: string
    quote_prefix: string
    quote_suffix: string
    hint_start: number | null
    expect_text: string | null
    result: [number, number, number] | null
  }[]
}

describe('normaliseForMatch', () => {
  it.each(fixtures.normalise.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    expect(normaliseForMatch(c.input)).toEqual({ text: c.text, starts: c.starts, ends: c.ends })
  })
})

describe('makeSelector', () => {
  it.each(fixtures.selector.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    expect(makeSelector(c.page_text, c.start, c.end)).toEqual(c.expected)
  })
  it('refuses an empty selection', () => {
    expect(() => makeSelector('abc', 2, 2)).toThrow(RangeError)
  })
})

describe('locateQuote', () => {
  it.each(fixtures.locate.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    const got = locateQuote(c.page_text, c.quote_exact, c.quote_prefix, c.quote_suffix, c.hint_start)
    if (c.result === null) {
      expect(got).toBeNull()
      return
    }
    expect(got).toEqual({ start: c.result[0], end: c.result[1], score: c.result[2] })
    expect(c.page_text.slice(c.result[0], c.result[1])).toBe(c.expect_text)
    expect(c.result[2]).toBeGreaterThanOrEqual(MIN_SCORE)
  })

  it('covers removed characters in the original range', () => {
    const page = 'xx deduc-\ntion of tax yy'
    const got = locateQuote(page, 'deduction of tax')
    expect(page.slice(got?.start, got?.end)).toBe('deduc-\ntion of tax')
  })
})
