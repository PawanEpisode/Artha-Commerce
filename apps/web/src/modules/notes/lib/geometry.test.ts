import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  ERROR_CODES,
  geometryBbox,
  type MarkKind,
  mergeAdjacentQuads,
  type Rect,
  round5,
  serialisedSize,
  validateGeometry,
} from './geometry'

interface Case {
  name: string
  kind: string | null
  geometry?: unknown
  gen?: { strokes: number; points: number; w?: number }
  errors: string[]
  expected: Record<string, unknown> | null
}

// The same fixtures the Python tests use: the two implementations must agree on every case.
const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/notes/tests/fixtures/geometry_cases.json', import.meta.url)),
    'utf8',
  ),
) as {
  cases: Case[]
  merge: { name: string; quads: Rect[]; expected: Rect[] }[]
  bbox: { name: string; kind: MarkKind; geometry: never; expected: Rect }[]
  size: { name: string; value: unknown; expected: number }[]
}

/** Deterministic big drawings, generated the same way as in the Python test. */
function inkFrom(spec: { strokes: number; points: number; w?: number }) {
  const five = (v: number) => Number(v.toFixed(5))
  return {
    strokes: Array.from({ length: spec.strokes }, (_, s) => ({
      pts: Array.from({ length: spec.points }, (_, i) => [
        five(((i * 7919 + s * 104729) % 99991) / 99991),
        five(((i * 6271 + s * 7) % 99989) / 99989),
      ]),
      w: spec.w ?? 0.0035,
    })),
  }
}

describe('validateGeometry', () => {
  it.each(fixtures.cases.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const result = validateGeometry(c.kind as string, c.gen ? inkFrom(c.gen) : c.geometry)
    expect(result.errors.map((e) => e.code)).toEqual(c.errors)
    expect(result.errors.every((e) => e.message.length > 0)).toBe(true)
    if (c.gen && c.expected) {
      const got = result.geometry as { strokes: unknown[]; bbox: Rect }
      expect({ size: serialisedSize(got), strokes: got.strokes.length, bbox: got.bbox }).toEqual(c.expected)
    } else {
      expect(result.geometry).toEqual(c.expected)
    }
  })

  it('only reports documented codes and normalising twice changes nothing', () => {
    for (const c of fixtures.cases) {
      for (const code of c.errors) expect(ERROR_CODES).toContain(code)
      if (c.expected && !c.gen) {
        expect(validateGeometry(c.kind as string, c.expected)).toEqual({ geometry: c.expected, errors: [] })
      }
    }
  })

  it('does not trust a prototype key as a kind', () => {
    expect(validateGeometry('constructor', {}).errors[0]?.code).toBe('bad_kind')
  })
})

describe('mergeAdjacentQuads', () => {
  it.each(fixtures.merge.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    expect(mergeAdjacentQuads(c.quads)).toEqual(c.expected)
  })
})

describe('geometryBbox and serialisedSize', () => {
  it.each(fixtures.bbox.map((c) => [c.name, c] as const))('bbox: %s', (_name, c) => {
    expect(geometryBbox(c.kind, c.geometry)).toEqual(c.expected)
  })

  it.each(fixtures.size.map((c) => [c.name, c] as const))('size: %s', (_name, c) => {
    expect(serialisedSize(c.value)).toBe(c.expected)
  })
})

describe('round5', () => {
  it('rounds half up on the decimal value', () => {
    expect(round5(0.123455)).toBe(0.12346)
    expect(round5(0.2)).toBe(0.2)
    expect(round5(0.015914)).toBe(0.01591)
  })
})
