import { describe, expect, it } from 'vitest'

import type { OcrWord } from '../document-types'
import { ocrTextContent, wordOffsets } from './ocr-text-layer'

const words: OcrWord[] = [
  [0.1, 0.1, 0.05, 0.012, 'ITC'],
  [0.17, 0.1, 0.04, 0.012, 'is'],
  [0.23, 0.1, 0.08, 0.012, 'blocked'],
  [0.1, 0.13, 0.1, 0.012, 'vehicles.'],
]
const text = 'ITC is blocked\nvehicles.'

describe('OCR text layer', () => {
  it('finds each word in the page text', () => {
    expect(wordOffsets(text, words)).toEqual([0, 4, 7, 15])
  })

  it('positions the words in the normalised frame as the same items native text uses', () => {
    const content = ocrTextContent({ text, words })
    expect(content?.text).toBe(text)
    expect(content?.items.map((i) => i.str)).toEqual(['ITC', 'is', 'blocked', 'vehicles.'])
    expect(content?.items[2]).toEqual({ str: 'blocked', x: 0.23, y: 0.1, w: 0.08, h: 0.012, angle: 0, start: 7 })
    for (const item of content?.items ?? []) expect(text.slice(item.start, item.start + item.str.length)).toBe(item.str)
  })

  it('matches case-insensitively and survives a word the text lacks', () => {
    expect(
      wordOffsets('itc is Blocked', [
        [0, 0, 0, 0, 'ITC'],
        [0, 0, 0, 0, 'ghost'],
        [0, 0, 0, 0, 'blocked'],
      ]),
    ).toEqual([0, 3, 7])
  })

  it('has no layer for a page without word boxes', () => {
    expect(ocrTextContent({ text, words: null })).toBeNull()
    expect(ocrTextContent({ text, words: [] })).toBeNull()
  })

  it('keeps Devanagari words', () => {
    const hi: OcrWord[] = [
      [0.1, 0.1, 0.1, 0.02, 'इनपुट'],
      [0.22, 0.1, 0.1, 0.02, 'क्रेडिट'],
    ]
    expect(wordOffsets('इनपुट क्रेडिट', hi)).toEqual([0, 6])
  })
})
