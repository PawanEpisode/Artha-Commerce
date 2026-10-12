import { describe, expect, it } from 'vitest'

import { contextPatch, storedPickerValue } from './context'

describe('storedPickerValue', () => {
  it('shows a stored subject with no chapter as "All chapters"', () => {
    const v = storedPickerValue({ subject_id: 's', chapter_id: null, activity_type: 'reading' })
    expect(v).toMatchObject({ subject_id: 's', chapter_id: null, all_chapters: true })
  })
  it('keeps a chapter, and leaves "no subject" unset', () => {
    expect(storedPickerValue({ subject_id: 's', chapter_id: 'c', activity_type: 'reading' }).all_chapters).toBe(false)
    expect(storedPickerValue({ subject_id: null, chapter_id: null, activity_type: 'reading' }).all_chapters).toBe(false)
  })
})

describe('contextPatch', () => {
  it('drops the UI-only flag and keeps chapter_id null for "All chapters"', () => {
    expect(contextPatch({ chapter_id: null, all_chapters: true })).toEqual({ chapter_id: null })
    expect(contextPatch({ subject_id: 's', chapter_id: null, all_chapters: false })).toEqual({
      subject_id: 's',
      chapter_id: null,
    })
  })
})
