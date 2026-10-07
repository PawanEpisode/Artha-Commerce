import { describe, expect, it } from 'vitest'

import {
  buildSelection,
  isUnfiled,
  linkFields,
  linkLabel,
  pickerReduce,
  sameLink,
  selectionFromLink,
  selectionFromSuggestion,
  shortLinkLabel,
} from './chapter-link'
import { FILED_LINK, UNFILED_LINK } from './testing'

const subjects = [{ id: 's1', key: 'taxation', name: 'Taxation' }]
const chapters = [{ id: 'c1', key: 'gst-itc', name: 'GST: Input tax credit' }]
const topics = [{ id: 't1', key: 'section-17', name: 'Section 17(5)' }]

describe('picker state', () => {
  const start = { subjectId: 's1', chapterId: 'c1', topicId: 't1' }

  it('clears the chapter and topic when the subject changes', () => {
    expect(pickerReduce(start, { subjectId: 's2' })).toEqual({ subjectId: 's2', chapterId: '', topicId: '' })
  })

  it('clears only the topic when the chapter changes', () => {
    expect(pickerReduce(start, { chapterId: 'c2' })).toEqual({ subjectId: 's1', chapterId: 'c2', topicId: '' })
  })

  it('keeps everything when the same subject is chosen again', () => {
    expect(pickerReduce(start, { subjectId: 's1' })).toEqual(start)
  })

  it('sets a topic inside the chapter', () => {
    expect(pickerReduce({ ...start, topicId: '' }, { topicId: 't1' }).topicId).toBe('t1')
  })
})

describe('buildSelection', () => {
  it('saves ids and stable keys for the chosen chapter and topic', () => {
    const sel = buildSelection('L', { subjectId: 's1', chapterId: 'c1', topicId: 't1' }, subjects, chapters, topics)
    expect(sel).toMatchObject({
      levelId: 'L',
      subjectKey: 'taxation',
      chapterId: 'c1',
      chapterKey: 'gst-itc',
      topicId: 't1',
      topicKey: 'section-17',
    })
  })

  it('is null until a chapter is chosen, and ignores a topic that is not in the list', () => {
    expect(buildSelection('L', { subjectId: 's1', chapterId: '', topicId: '' }, subjects, chapters, topics)).toBeNull()
    expect(
      buildSelection('L', { subjectId: 's1', chapterId: 'c1', topicId: 'zz' }, subjects, chapters, topics)?.topicId,
    ).toBeNull()
  })
})

describe('links', () => {
  it('writes chapter and topic ids, or nulls to unfile', () => {
    const sel = selectionFromLink({
      ...FILED_LINK,
      topic_id: 't1',
      topic_key: 'section-17',
      topic_name: 'Section 17(5)',
    })!
    expect(linkFields(sel)).toEqual({ chapter_id: 'c1', topic_id: 't1' })
    expect(linkFields(null)).toEqual({ chapter_id: null, topic_id: null })
  })

  it('reads a selection back from a note link, and gives null for an unfiled one', () => {
    expect(selectionFromLink(FILED_LINK)?.chapterKey).toBe('gst-itc')
    expect(selectionFromLink(UNFILED_LINK)).toBeNull()
  })

  it('words the link', () => {
    expect(linkLabel(FILED_LINK)).toBe('Taxation › GST: Input tax credit')
    expect(linkLabel(UNFILED_LINK)).toBe('Unfiled')
    expect(shortLinkLabel(FILED_LINK)).toBe('GST: Input tax credit')
    expect(isUnfiled(UNFILED_LINK)).toBe(true)
  })

  it('knows when a pick changes nothing', () => {
    expect(sameLink(selectionFromLink(FILED_LINK), FILED_LINK)).toBe(true)
    expect(sameLink(null, UNFILED_LINK)).toBe(true)
    expect(sameLink(null, FILED_LINK)).toBe(false)
  })

  it('builds a selection from a server suggestion', () => {
    const sel = selectionFromSuggestion(
      {
        chapter_id: 'c1',
        chapter_key: 'gst-itc',
        chapter_name: 'GST ITC',
        subject_id: 's1',
        subject_key: 'taxation',
        subject_name: 'Taxation',
        score: 3,
      },
      'L',
    )
    expect(sel).toMatchObject({ levelId: 'L', chapterId: 'c1', topicId: null })
  })
})
