import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { checkName, firstNameOf } from './names'

const { cases } = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/profiles/tests/fixtures/names_cases.json', import.meta.url)),
    'utf8',
  ),
) as { cases: Array<{ name: string; input: string; ok: boolean; expected: string }> }

describe('shared name cases', () => {
  it.each(cases)('$name', ({ input, ok, expected }) => {
    const result = checkName(input)
    expect(result.ok).toBe(ok)
    expect(result.ok ? result.name : result.message).toBe(expected)
  })
})

describe('firstNameOf', () => {
  it('takes the first word', () => {
    expect(firstNameOf('Aarav Kumar Mehta')).toBe('Aarav')
    expect(firstNameOf('')).toBe('')
  })
})
