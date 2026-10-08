import { describe, expect, it } from 'vitest'

import { canSaveAsNote, isReplaceActive, kindText, openCount, reasonText, replaceStatusText } from './replace-copy'
import type { AttentionItem } from './replace-types'

const stats = (over = {}) => ({ total: 5, attached: 3, moved: 1, needs_attention: 1, ranges_copied: 0, ...over })
const item = (over: Partial<AttentionItem> = {}): AttentionItem => ({
  id: 'i1',
  source_annotation_id: 'a1',
  kind: 'highlight',
  page: 3,
  color: 'y',
  quote: 'tax credit',
  comment: '',
  reason: 'not_found',
  status: 'open',
  new_annotation_id: null,
  result_note_id: null,
  resolved_at: null,
  ...over,
})

describe('replace edition copy', () => {
  it('says nothing for a document that is not a newer edition', () => {
    expect(replaceStatusText({ reanchor_status: 'none', reanchor: null })).toBeNull()
  })

  it('words each stage of moving the marks', () => {
    expect(replaceStatusText({ reanchor_status: 'waiting', reanchor: null })).toMatch(/as soon as/)
    expect(replaceStatusText({ reanchor_status: 'running', reanchor: null })).toMatch(/Moving your marks/)
    expect(replaceStatusText({ reanchor_status: 'failed', reanchor: null })).toMatch(/still on the old edition/)
  })

  it('counts what moved and what needs attention, with singular and plural', () => {
    expect(replaceStatusText({ reanchor_status: 'done', reanchor: stats() })).toBe(
      '4 marks moved to this edition. 1 mark need your attention.',
    )
    expect(
      replaceStatusText({ reanchor_status: 'done', reanchor: stats({ attached: 1, moved: 0, needs_attention: 0 }) }),
    ).toBe('1 mark moved to this edition.')
    expect(replaceStatusText({ reanchor_status: 'done', reanchor: stats({ total: 0 }) })).toMatch(/no marks/)
  })

  it('knows when the server is still working', () => {
    expect(isReplaceActive({ reanchor_status: 'running', reanchor: null })).toBe(true)
    expect(isReplaceActive({ reanchor_status: 'done', reanchor: null })).toBe(false)
  })

  it('explains every reason in plain words and has a fallback', () => {
    for (const r of ['not_found', 'low_score', 'page_changed', 'no_page', 'cannot_compare'])
      expect(reasonText(r)).not.toBe(reasonText('something-new'))
    expect(kindText('sticky')).toBe('Sticky note')
    expect(kindText('mystery')).toBe('Mark')
  })

  it('offers "save as a note" only when there is something to save, and counts what is still open', () => {
    expect(canSaveAsNote(item())).toBe(true)
    expect(canSaveAsNote(item({ quote: '', comment: '  ' }))).toBe(false)
    expect(openCount([item(), item({ id: 'i2', status: 'kept' })])).toBe(1)
  })
})
