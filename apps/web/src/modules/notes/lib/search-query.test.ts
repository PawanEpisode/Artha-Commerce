import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  isSearchable,
  normaliseQuery,
  prepareQuery,
  queryLengthBucket,
  queryTerms,
  resultBucket,
  splitHighlight,
} from './search-query'

describe('normaliseQuery', () => {
  it('trims, collapses spaces and cuts at 200 characters', () => {
    expect(normaliseQuery('  section   17(5)  ')).toBe('section 17(5)')
    expect([...normaliseQuery('a'.repeat(300))]).toHaveLength(200)
    expect([...normaliseQuery('😀'.repeat(250))]).toHaveLength(200)
  })

  it('knows an empty query is not searchable', () => {
    expect(isSearchable('   ')).toBe(false)
    expect(isSearchable('itc')).toBe(true)
  })
})

describe('queryTerms', () => {
  it('keeps references and quoted phrases whole, longest first, without duplicates', () => {
    expect(queryTerms('17(5) "blocked credit" ITC itc')).toEqual(['blocked credit', '17(5)', 'itc'])
  })
})

describe('splitHighlight', () => {
  it('splits a snippet into plain and matching pieces', () => {
    expect(splitHighlight('Credit under 17(5) is blocked', '17(5)')).toEqual([
      { text: 'Credit under ', match: false },
      { text: '17(5)', match: true },
      { text: ' is blocked', match: false },
    ])
  })

  it('matches without caring about case and escapes regex characters', () => {
    expect(splitHighlight('ITC and itc', 'itc').filter((p) => p.match)).toHaveLength(2)
    expect(splitHighlight('a.b', '.')).toEqual([
      { text: 'a', match: false },
      { text: '.', match: true },
      { text: 'b', match: false },
    ])
  })

  it('returns the text as is with no terms', () => {
    expect(splitHighlight('hello', '  ')).toEqual([{ text: 'hello', match: false }])
  })
})

describe('buckets', () => {
  it('reports the length of a query and the number of results only as ranges', () => {
    expect(queryLengthBucket('abc')).toBe('1-3')
    expect(queryLengthBucket('abcdefgh')).toBe('4-10')
    expect(queryLengthBucket('a'.repeat(20))).toBe('11-30')
    expect(queryLengthBucket('a'.repeat(50))).toBe('31+')
    expect([0, 3, 10, 40].map(resultBucket)).toEqual(['0', '1-5', '6-20', '21+'])
  })
})

// The same fixtures the Python tests use: the two implementations must agree on every case.
const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/notes/tests/fixtures/search_query_cases.json', import.meta.url)),
    'utf8',
  ),
) as { prepare: { input: string; expected: string }[]; clean: { input: string; expected: string }[] }

describe('prepareQuery (shared with the server)', () => {
  it.each(fixtures.prepare.map((c) => [c.input, c] as const))('%j', (_input, c) => {
    expect(prepareQuery(c.input)).toBe(c.expected)
  })

  it.each(fixtures.clean.map((c) => [c.input.slice(0, 12), c] as const))('normaliseQuery %j', (_input, c) => {
    expect(normaliseQuery(c.input)).toBe(c.expected)
  })
})
