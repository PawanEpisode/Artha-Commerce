import { describe, expect, it } from 'vitest'

import type { PdfSearchHit, SearchMeta } from './library-types'
import { groupPdfHits, indexingText, isMarkHit, isPdfHit, notSearchable } from './search-groups'
import { UNFILED_LINK } from './testing'

const hit = (document_id: string, page: number, rank: number, title = document_id): PdfSearchHit => ({
  type: 'pdf',
  document_id,
  document_title: title,
  page,
  snippet: `page ${page}`,
  rank,
  link: UNFILED_LINK,
})

describe('groupPdfHits', () => {
  it('groups by document, keeps the best document first, pages in page order', () => {
    const groups = groupPdfHits([hit('a', 9, 1), hit('b', 2, 2), hit('a', 3, 3)])
    expect(groups.map((g) => g.documentId)).toEqual(['a', 'b'])
    expect(groups[0]?.hits.map((h) => h.page)).toEqual([3, 9])
  })
  it('shows the top five pages of a document and counts the rest', () => {
    const many = Array.from({ length: 8 }, (_, i) => hit('a', 20 - i, i))
    const [group] = groupPdfHits(many)
    expect(group?.hits).toHaveLength(5)
    expect(group?.more).toBe(3)
    expect(group?.hits.map((h) => h.page)).toEqual([16, 17, 18, 19, 20])
  })
  it('tells the hit kinds apart', () => {
    expect(isPdfHit({ type: 'pdf' })).toBe(true)
    expect(isMarkHit({ type: 'highlight' })).toBe(true)
    expect(isMarkHit({ type: 'note' })).toBe(false)
  })
})

describe('meta messages', () => {
  const meta = (n: number, rows: SearchMeta['not_searchable'] = []): SearchMeta => ({
    indexing_documents: n,
    not_searchable: rows,
  })
  it('says how many documents are still being indexed', () => {
    expect(indexingText(undefined)).toBeNull()
    expect(indexingText(meta(0))).toBeNull()
    expect(indexingText(meta(1))).toBe('1 document is still being indexed.')
    expect(indexingText(meta(2))).toBe('2 documents are still being indexed.')
  })
  it('names why documents cannot be searched, and leaves pending ones to the indexing line', () => {
    expect(notSearchable(meta(0))).toBeNull()
    expect(notSearchable(meta(1, [{ document_id: 'a', reason: 'pending' }]))).toBeNull()
    expect(notSearchable(meta(0, [{ document_id: 'a', reason: 'scanned' }]))).toMatchObject({
      total: 1,
      scanned: 1,
      text: '1 document cannot be searched yet (scanned).',
    })
    expect(
      notSearchable(
        meta(0, [
          { document_id: 'a', reason: 'scanned' },
          { document_id: 'b', reason: 'locked' },
        ]),
      )?.text,
    ).toBe('2 documents cannot be searched yet (locked or scanned).')
  })
})
