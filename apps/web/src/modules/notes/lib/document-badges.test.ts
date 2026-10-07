import { describe, expect, it } from 'vitest'

import { canOpenDocument, documentBadges, documentTitle, isWorking, readPercent } from './document-badges'
import { makeDocument } from './testing-documents'

const kinds = (over: Parameters<typeof makeDocument>[0], opts?: { offlineCopy?: boolean }) =>
  documentBadges(makeDocument(over), opts).map((b) => b.kind)

describe('document badges: always words, in order', () => {
  it('shows each status', () => {
    expect(kinds({ status: 'ready' })).toEqual(['ready'])
    expect(kinds({ status: 'scanning' })).toEqual(['preparing'])
    expect(kinds({ status: 'needs_password' })).toEqual(['locked'])
    expect(kinds({ status: 'rejected' })).toEqual(['rejected'])
    expect(kinds({ status: 'failed' })).toEqual(['failed'])
    expect(kinds({ status: 'expired' })).toEqual(['expired'])
    expect(kinds({ status: 'reserved' })).toEqual(['waiting'])
  })
  it('walks a scanned file through OCR', () => {
    expect(kinds({ is_scanned: true, ocr_status: 'none' })).toEqual(['ready', 'scanned'])
    expect(kinds({ is_scanned: true, ocr_status: 'running', ocr_pages_done: 4, ocr_pages_total: 10 })).toEqual([
      'ready',
      'ocr',
    ])
    expect(kinds({ is_scanned: true, ocr_status: 'done' })).toEqual(['ready', 'searchable'])
    expect(kinds({ is_scanned: true, ocr_status: 'failed' })).toEqual(['ready', 'ocr_failed'])
    expect(
      documentBadges(
        makeDocument({ is_scanned: true, ocr_status: 'running', ocr_pages_done: 4, ocr_pages_total: 10 }),
      )[1]?.label,
    ).toBe('OCR 4 of 10')
  })
  it('labels an offline copy', () => expect(kinds({}, { offlineCopy: true })).toEqual(['ready', 'offline']))
})

describe('document helpers', () => {
  it('reads progress only after a first open', () => {
    expect(readPercent(makeDocument({ last_opened_at: null }))).toBeNull()
    expect(readPercent(makeDocument({ last_opened_at: '2026-10-01T00:00:00Z', last_page: 25, page_count: 100 }))).toBe(
      25,
    )
    expect(readPercent(makeDocument({ last_opened_at: '2026-10-01T00:00:00Z', last_page: 500, page_count: 100 }))).toBe(
      100,
    )
  })
  it('polls while the server works, but not for a reservation that never finished', () => {
    expect(isWorking({ status: 'scanning', ocr_status: 'none' })).toBe(true)
    expect(isWorking({ status: 'ready', ocr_status: 'running' })).toBe(true)
    expect(isWorking({ status: 'reserved', ocr_status: 'none' })).toBe(false)
    expect(isWorking({ status: 'ready', ocr_status: 'none' })).toBe(false)
  })
  it('opens ready and locked files, with a title stand-in', () => {
    expect(canOpenDocument({ status: 'ready' })).toBe(true)
    expect(canOpenDocument({ status: 'needs_password' })).toBe(true)
    expect(canOpenDocument({ status: 'rejected' })).toBe(false)
    expect(documentTitle({ title: ' ', original_filename: 'a.pdf' })).toBe('a.pdf')
    expect(documentTitle({ title: '', original_filename: '' })).toBe('Untitled PDF')
  })
})
