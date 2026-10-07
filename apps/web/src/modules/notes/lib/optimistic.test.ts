import { describe, expect, it } from 'vitest'

import { linkFromSelection } from './chapter-link'
import { applyLocalEdit } from './optimistic'
import { makeNote, UNFILED_LINK } from './testing'

describe('applyLocalEdit', () => {
  it('updates text, snippet and size together and keeps the revision', () => {
    const note = makeNote({ rev: 4 })
    const next = applyLocalEdit(note, { body_md: '# Heading\n\nSome **bold** text' }, '2026-10-02T00:00:00Z')
    expect(next.rev).toBe(4)
    expect(next.updated_at).toBe('2026-10-02T00:00:00Z')
    expect(next.body_chars).toBe(29)
    expect(next.snippet).not.toContain('**')
  })

  it('changes only the fields it is given', () => {
    const note = makeNote({ pinned: false, title: 'A' })
    expect(applyLocalEdit(note, { pinned: true }).title).toBe('A')
    expect(applyLocalEdit(note, { pinned: true }).pinned).toBe(true)
  })

  it('builds the link of a selection, and an all-null link for none', () => {
    expect(linkFromSelection(null)).toEqual(UNFILED_LINK)
    const link = linkFromSelection({
      levelId: 'l',
      subjectId: 's',
      subjectKey: 'sk',
      subjectName: 'Subject',
      chapterId: 'c',
      chapterKey: 'ck',
      chapterName: 'Chapter',
      topicId: null,
      topicKey: null,
      topicName: null,
    })
    expect(link.chapter_key).toBe('ck')
    expect(link.topic_id).toBeNull()
    expect(link.moved_or_removed).toBe(false)
  })
})
