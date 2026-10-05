import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { cleanVisit, isRestorable, visitHref } from './restorable'

const { cases } = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/profiles/tests/fixtures/restorable_cases.json', import.meta.url)),
    'utf8',
  ),
) as { cases: Array<{ name: string; path: string; search: string; expected: { path: string; search: string } | null }> }

describe('shared restorable cases (same file as the API tests)', () => {
  it.each(cases)('$name', ({ path, search, expected }) => {
    expect(cleanVisit(path, search)).toEqual(expected)
  })
})

describe('helpers', () => {
  it('isRestorable takes a full target', () => {
    expect(isRestorable('/app/tracker/reports?range=7d')).toBe(true)
    expect(isRestorable('/app/account')).toBe(false)
  })
  it('visitHref joins path and search', () => {
    expect(visitHref({ path: '/app/focus', search: '' })).toBe('/app/focus')
    expect(visitHref({ path: '/app/tracker/reports', search: 'range=7d' })).toBe('/app/tracker/reports?range=7d')
  })
})
