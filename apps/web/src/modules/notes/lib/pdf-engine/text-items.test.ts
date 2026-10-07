import { describe, expect, it } from 'vitest'

import { buildTextModel, multiply, pageTextOf, runFromPdfItem } from './text-items'

describe('buildTextModel', () => {
  const run = (str: string, x: number, y: number, hasEOL = false) => ({
    str,
    x,
    y,
    width: str.length * 6,
    fontSize: 12,
    angle: 0,
    hasEOL,
  })

  it('places upright text in the normalised frame with the line box above the baseline', () => {
    const m = buildTextModel([run('Input', 100, 200)], 600, 800)
    const item = m.items[0]
    expect(item?.x).toBeCloseTo(100 / 600, 4)
    expect(item?.y).toBeCloseTo((200 - 0.8 * 12) / 800, 4)
    expect(item?.w).toBeCloseTo(30 / 600, 4)
    expect(item?.h).toBeCloseTo(12 / 800, 4)
  })

  it('builds the page text with a newline after each line end and offsets that index into it', () => {
    const m = buildTextModel([run('Input ', 0, 20), run('tax', 40, 20, true), run('credit', 0, 40, true)], 600, 800)
    expect(m.text).toBe('Input tax\ncredit\n')
    expect(m.items.map((i) => m.text.slice(i.start, i.start + i.str.length))).toEqual(['Input ', 'tax', 'credit'])
  })

  it('skips empty runs but keeps their line break, and never doubles a newline', () => {
    const m = buildTextModel([run('a', 0, 0, true), run('', 0, 0, true), run('b', 0, 20)], 600, 800)
    expect(m.text).toBe('a\nb')
    expect(m.items).toHaveLength(2)
  })

  it('matches the plain page text used by search', () => {
    const runs = [run('Input ', 0, 20), run('tax', 40, 20, true), run('credit', 0, 40, true)]
    expect(pageTextOf(runs)).toBe(buildTextModel(runs, 600, 800).text)
  })

  it('keeps Devanagari intact', () => {
    const m = buildTextModel([run('इनपुट टैक्स क्रेडिट', 0, 20)], 600, 800)
    expect(m.text).toBe('इनपुट टैक्स क्रेडिट')
  })
})

describe('runFromPdfItem', () => {
  // pdf.js viewport at scale 1 for an unrotated 600 x 800 page: flips y.
  const viewport = [1, 0, 0, -1, 0, 800]

  it('reads position, font size and width from the matrices', () => {
    const r = runFromPdfItem({ str: 'x', transform: [12, 0, 0, 12, 100, 600], width: 30, hasEOL: false }, viewport)
    expect(r.x).toBe(100)
    expect(r.y).toBe(200)
    expect(r.fontSize).toBe(12)
    expect(r.width).toBe(30)
    expect(r.angle).toBeCloseTo(0)
  })

  it('follows a page rotated a quarter turn clockwise', () => {
    // Rotate 90: user (x, y) -> displayed (y, x) for a page whose displayed size is 800 x 600.
    const rotated = [0, 1, 1, 0, 0, 0]
    const r = runFromPdfItem({ str: 'x', transform: [12, 0, 0, 12, 100, 600], width: 30, hasEOL: false }, rotated)
    expect(r.x).toBe(600)
    expect(r.y).toBe(100)
    expect(r.fontSize).toBe(12)
    expect(Math.abs(r.angle)).toBeCloseTo(Math.PI / 2)
  })

  it('multiplies matrices in pdf.js order', () => {
    expect(multiply([1, 0, 0, 1, 10, 20], [2, 0, 0, 2, 1, 1])).toEqual([2, 0, 0, 2, 11, 21])
  })
})
