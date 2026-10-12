import { describe, expect, it } from 'vitest'

import { hasSubjectAndChapter } from './ContextPicker'

describe('hasSubjectAndChapter', () => {
  it('needs a subject and either a chapter or "All chapters"', () => {
    expect(hasSubjectAndChapter({ subject_id: 's', chapter_id: null })).toBe(false)
    expect(hasSubjectAndChapter({ subject_id: 's', chapter_id: 'c' })).toBe(true)
    expect(hasSubjectAndChapter({ subject_id: 's', chapter_id: null, all_chapters: true })).toBe(true)
    expect(hasSubjectAndChapter({ subject_id: null, chapter_id: null, all_chapters: true })).toBe(false)
  })
})
