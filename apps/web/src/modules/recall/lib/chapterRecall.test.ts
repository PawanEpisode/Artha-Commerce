import { describe, expect, it } from 'vitest'

import { chapterReviewSearch, showsStrength, strengthSentence } from './chapterRecall'

const row = (over: Partial<{ percent: number | null; due: number; cards: number }> = {}) => ({
  chapter_id: 'c',
  strength: 0.82,
  percent: 82,
  due: 6,
  cards: 20,
  ...over,
})

describe('chapter recall card', () => {
  it('says the sentence of the spec', () => {
    expect(strengthSentence(row())).toBe('Recall strength 82%, 6 cards due')
  })
  it('says one card, nothing due, and not reviewed yet', () => {
    expect(strengthSentence(row({ due: 1 }))).toBe('Recall strength 82%, 1 card due')
    expect(strengthSentence(row({ due: 0 }))).toBe('Recall strength 82%, nothing due')
    expect(strengthSentence(row({ percent: null, due: 0, cards: 3 }))).toBe('Not reviewed yet, 3 cards to learn')
    expect(strengthSentence(row({ percent: null, due: 2, cards: 3 }))).toBe('Not reviewed yet, 2 cards due')
  })
  it('is hidden with the flag off, before the answer and with no cards', () => {
    expect(showsStrength(false, row())).toBe(false)
    expect(showsStrength(true, undefined)).toBe(false)
    expect(showsStrength(true, row({ cards: 0, due: 0, percent: null }))).toBe(false)
    expect(showsStrength(true, row())).toBe(true)
  })
  it('links with the chapter id only', () => {
    expect(chapterReviewSearch('abc')).toEqual({ chapter: 'abc' })
  })
})
