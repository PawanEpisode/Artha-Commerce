import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  denormaliseRect,
  fromViewportPoint,
  fromViewportRect,
  normaliseRect,
  normaliseRotation,
  rotatePoint,
  rotateRect,
  toViewportPoint,
  toViewportRect,
  unrotateRect,
  viewportSize,
  viewSize,
} from './coords'
import type { Rect } from './geometry'

type Named<T> = T & { name: string }
// The same fixtures the Python tests use: the two implementations must agree on every case.
const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/notes/tests/fixtures/coords_cases.json', import.meta.url)),
    'utf8',
  ),
) as {
  normalise: Named<{ page: [number, number]; pt: Rect; expected: Rect }>[]
  denormalise: Named<{ page: [number, number]; rect: Rect; expected: Rect }>[]
  rotate_rect: Named<{ rect: Rect; rotation: number; expected: Rect }>[]
  rotate_point: Named<{ pt: [number, number]; rotation: number; expected: [number, number] }>[]
  viewport: Named<{
    page: [number, number]
    zoom: number
    rotation: number
    rect: Rect
    size: [number, number]
    expected: Rect
  }>[]
  invalid_rotations: number[]
}
const cases = <T extends { name: string }>(list: T[]) => list.map((c) => [c.name, c] as const)

describe('normalise and denormalise', () => {
  it.each(cases(fixtures.normalise))('normalise: %s', (_n, c) => {
    expect(normaliseRect(...c.pt, ...c.page)).toEqual(c.expected)
  })
  it.each(cases(fixtures.denormalise))('denormalise: %s', (_n, c) => {
    denormaliseRect(c.rect, ...c.page).forEach((v, i) => expect(v).toBeCloseTo(c.expected[i] as number, 9))
  })
})

describe('rotation', () => {
  it.each(cases(fixtures.rotate_rect))('%s', (_n, c) => {
    expect(rotateRect(c.rect, c.rotation)).toEqual(c.expected)
  })
  it.each(cases(fixtures.rotate_point))('%s', (_n, c) => {
    expect(rotatePoint(c.pt, c.rotation)).toEqual(c.expected)
  })
  it.each([0, 90, 180, 270])('unrotate undoes rotate at %i', (r) => {
    expect(unrotateRect(rotateRect([0.1, 0.2, 0.3, 0.05], r), r)).toEqual([0.1, 0.2, 0.3, 0.05])
  })
  it('rejects anything but a multiple of 90 and wraps the rest', () => {
    for (const bad of fixtures.invalid_rotations) expect(() => normaliseRotation(bad)).toThrow(RangeError)
    expect(normaliseRotation(-90)).toBe(270)
    expect(normaliseRotation(450)).toBe(90)
    expect(viewSize(595, 842, 90)).toEqual([842, 595])
  })
})

describe('viewport transforms', () => {
  it.each(cases(fixtures.viewport))('%s', (_n, c) => {
    const view = { width: c.size[0], height: c.size[1], rotation: c.rotation }
    expect(viewportSize(c.page[0], c.page[1], c.zoom, c.rotation)).toEqual({ width: c.size[0], height: c.size[1] })
    const px = toViewportRect(c.rect, view)
    px.forEach((v, i) => expect(v).toBeCloseTo(c.expected[i] as number, 6))
    // and a drag in the viewport comes back as the stored rectangle
    fromViewportRect(px, view).forEach((v, i) => expect(v).toBeCloseTo(c.rect[i] as number, 5))
  })

  it('maps a point both ways at every rotation and zoom', () => {
    for (const rotation of [0, 90, 180, 270]) {
      const size = viewportSize(595, 842, 1.25, rotation)
      const view = { ...size, rotation }
      const back = fromViewportPoint(toViewportPoint([0.3, 0.6], view), view)
      expect(back[0]).toBeCloseTo(0.3, 5)
      expect(back[1]).toBeCloseTo(0.6, 5)
    }
  })

  it('keeps a mark on the same words when only the zoom changes', () => {
    const rect: Rect = [0.2, 0.2, 0.4, 0.01591]
    const a = toViewportRect(rect, { width: 595, height: 842, rotation: 0 })
    const b = toViewportRect(rect, { width: 1190, height: 1684, rotation: 0 })
    a.forEach((v, i) => expect(v * 2).toBeCloseTo(b[i] as number, 9))
  })
})
