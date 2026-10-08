import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import * as limits from './limits'

/** Parse the plain `NAME = literal` lines of the Python limits file into JSON values. */
function pythonConstants(): Record<string, unknown> {
  const text = readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/recall/domain/limits.py', import.meta.url)),
    'utf8',
  )
  const out: Record<string, unknown> = {}
  for (const line of text.split('\n')) {
    const m = /^([A-Z][A-Z0-9_]*)(?:, ([A-Z][A-Z0-9_, ]*))? = ([^#]+?)\s*(?:#.*)?$/.exec(line)
    if (!m) continue
    const names = [m[1]!, ...(m[2] ? m[2].split(', ') : [])]
    const raw = m[3]!.trim()
    const json = raw
      .replace(/\(/g, '[')
      .replace(/\)/g, ']')
      .replace(/,\s*\]/g, ']')
      .replace(/(\d)_(?=\d)/g, '$1')
    if (names.length === 1) out[names[0]!] = JSON.parse(json.startsWith('"') ? json : json)
    else {
      const values = JSON.parse(`[${json}]`) as unknown[]
      names.forEach((n, i) => (out[n] = values[i]))
    }
  }
  return out
}

describe('limits parity with the Python domain', () => {
  const py = pythonConstants()
  it('finds the constants it should', () => {
    expect(Object.keys(py).length).toBeGreaterThan(50)
  })
  it('has every Python constant with the same value', () => {
    const ts = limits as Record<string, unknown>
    for (const [name, value] of Object.entries(py)) {
      expect(ts[name], name).toEqual(value)
    }
  })
  it('has no constant the Python side lacks', () => {
    expect(Object.keys(limits).filter((n) => !(n in py))).toEqual([])
  })
})
