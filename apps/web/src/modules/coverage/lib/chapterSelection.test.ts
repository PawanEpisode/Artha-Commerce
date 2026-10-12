import { describe, expect, it } from 'vitest'

import { chapterSelectionOf, chapterSelectValue, isChapterUnset, storedChapterSelection } from './chapterSelection'
import { ALL_CHAPTERS } from './subjects'

describe('chapter selection', () => {
  it('maps select values to a choice and back', () => {
    expect(chapterSelectionOf('')).toEqual({ chapter_id: null, all_chapters: false })
    expect(chapterSelectionOf(ALL_CHAPTERS)).toEqual({ chapter_id: null, all_chapters: true })
    expect(chapterSelectionOf('c1')).toEqual({ chapter_id: 'c1', all_chapters: false })
    for (const v of ['', ALL_CHAPTERS, 'c1']) expect(chapterSelectValue(chapterSelectionOf(v))).toBe(v)
  })

  it('is unset only with neither a chapter nor "All chapters"', () => {
    expect(isChapterUnset({ chapter_id: null, all_chapters: false })).toBe(true)
    expect(isChapterUnset({ chapter_id: null, all_chapters: true })).toBe(false)
    expect(isChapterUnset({ chapter_id: 'c', all_chapters: false })).toBe(false)
  })

  it('reads a stored subject without a chapter as the whole subject', () => {
    expect(storedChapterSelection('s', null)).toEqual({ chapter_id: null, all_chapters: true })
    expect(storedChapterSelection('s', 'c')).toEqual({ chapter_id: 'c', all_chapters: false })
    expect(storedChapterSelection(null, null)).toEqual({ chapter_id: null, all_chapters: false })
  })
})
