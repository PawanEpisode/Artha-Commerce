import { describe, expect, it } from 'vitest'

import { ALL_CHAPTERS } from '~/modules/coverage'

import {
  documentPatch,
  draftFromDocument,
  draftFromFile,
  EMPTY_FILING,
  filingFromDocument,
  filingProblem,
  firstInvalidStep,
  selectionOfDraft,
  titleFromFilename,
  uploadDetails,
} from './document-draft'
import { emptyRow } from './page-ranges'
import { FILED_LINK } from './testing'
import { makeDocument } from './testing-documents'

const subjects = [{ id: 's-now', key: 'taxation', name: 'Taxation' }]
const chapters = [{ id: 'c1', key: 'gst', name: 'GST' }]

describe('titleFromFilename', () => {
  it('drops folders and the extension and turns underscores into spaces', () => {
    expect(titleFromFilename('C:\\notes\\Transfer_Pricing__Saviour.pdf')).toBe('Transfer Pricing Saviour')
    expect(titleFromFilename('')).toBe('Untitled PDF')
    expect(titleFromFilename('.pdf')).toBe('Untitled PDF')
  })
})

describe('filing', () => {
  it('reads a chapter filing, finding the subject by its key', () => {
    const doc = makeDocument({ link: { ...FILED_LINK, subject_key: 'taxation', subject_id: 's-old' } })
    expect(filingFromDocument(doc, subjects).subjectId).toBe('s-now')
  })

  it('reads subject-level filing as All chapters', () => {
    const doc = makeDocument({
      link: { ...FILED_LINK, chapter_id: null, chapter_key: null, chapter_name: null, topic_id: null },
    })
    expect(filingFromDocument(doc, subjects).chapterId).toBe(ALL_CHAPTERS)
  })

  it('is empty for an unfiled document', () => {
    expect(filingFromDocument(makeDocument(), subjects)).toEqual(EMPTY_FILING)
  })

  it('asks for a chapter once a subject is chosen', () => {
    expect(filingProblem({ subjectId: 's1', chapterId: '', topicId: '' })).toMatch(/All chapters/)
    expect(filingProblem({ subjectId: 's1', chapterId: ALL_CHAPTERS, topicId: '' })).toBeNull()
    expect(filingProblem(EMPTY_FILING)).toBeNull()
  })

  it('builds a selection: null for unfiled, undefined while loading, a subject-level one for All chapters', () => {
    expect(selectionOfDraft('L', EMPTY_FILING, subjects, [], [])).toBeNull()
    expect(selectionOfDraft(undefined, { subjectId: 's-now', chapterId: 'c1', topicId: '' }, subjects, [], [])).toBe(
      undefined,
    )
    expect(
      selectionOfDraft('L', { subjectId: 's-now', chapterId: ALL_CHAPTERS, topicId: '' }, subjects, chapters, []),
    ).toMatchObject({ subjectKey: 'taxation', chapterId: null })
  })
})

describe('documentPatch', () => {
  const doc = makeDocument({ title: 'Old title' })
  const draft = draftFromDocument(doc, subjects)

  it('is null when nothing changed', () => {
    expect(documentPatch(doc, draft, null)).toBeNull()
  })

  it('sends only what changed, with base_rev', () => {
    expect(documentPatch(doc, { ...draft, title: '  New title ', edition_label: ' 2027 ' }, null)).toEqual({
      base_rev: doc.rev,
      title: 'New title',
      edition_label: '2027',
    })
  })

  it('files under the whole subject with the subject id and no chapter', () => {
    const selection = selectionOfDraft(
      'L',
      { subjectId: 's-now', chapterId: ALL_CHAPTERS, topicId: '' },
      subjects,
      chapters,
      [],
    )
    expect(documentPatch(doc, draft, selection)).toEqual({
      base_rev: doc.rev,
      chapter_id: null,
      topic_id: null,
      subject_id: 's-now',
    })
  })

  it('leaves the filing alone while its lists are loading', () => {
    expect(documentPatch(doc, draft, undefined)).toBeNull()
  })
})

describe('upload details and validation', () => {
  it('sends a title only when the student changed it, and no empty fields', () => {
    const draft = draftFromFile('Transfer_Pricing.pdf')
    expect(uploadDetails(draft, 'Transfer_Pricing.pdf')).toEqual({})
    expect(
      uploadDetails({ ...draft, title: 'TP', edition_label: '2027', tag_ids: ['t1'] }, 'Transfer_Pricing.pdf'),
    ).toEqual({ title: 'TP', edition_label: '2027', tag_ids: ['t1'] })
  })

  it('finds the first step with something to fix', () => {
    const draft = draftFromFile('a.pdf')
    expect(firstInvalidStep(draft, 10)).toBeNull()
    expect(firstInvalidStep({ ...draft, title: ' ' }, 10)).toBe('details')
    expect(firstInvalidStep({ ...draft, filing: { subjectId: 's', chapterId: '', topicId: '' } }, 10)).toBe('filing')
    expect(firstInvalidStep({ ...draft, rows: [{ ...emptyRow('1'), to: '99', chapterId: 'c1' }] }, 10)).toBe('ranges')
    // A blank row the student never touched is not a mistake.
    expect(firstInvalidStep({ ...draft, rows: [emptyRow()] }, 10)).toBeNull()
  })
})
