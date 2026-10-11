import { describe, expect, it } from 'vitest'

import type { SyncResult } from './schemas'
import {
  appliedMessage,
  bannerHelp,
  bannerTitle,
  changesText,
  kindsIn,
  moreText,
  recheckHelp,
  recheckLabel,
  relationText,
  returningText,
} from './updates'

const result = (over: Partial<SyncResult> = {}): SyncResult => ({
  changed: true,
  from_version_no: 1,
  to_version_no: 2,
  versions_skipped: 0,
  added: 0,
  removed: 0,
  silent: 0,
  rechecked: 0,
  cards_created: 0,
  cards_restored: 0,
  cards_archived: 0,
  cards_updated: 0,
  cards_reset: 0,
  ...over,
})

describe('living deck words', () => {
  it('counts changes in the singular and the plural', () => {
    expect(changesText(1)).toBe('1 change')
    expect(changesText(3)).toBe('3 changes')
    expect(bannerTitle(3)).toBe('Update available (3 changes)')
    expect(bannerTitle(0)).toBe('Update available')
  })

  it('says what follow and pin mean', () => {
    expect(bannerHelp(true)).toMatch(/applied for you/)
    expect(bannerHelp(false)).toMatch(/pinned/)
  })

  it('lists the kinds present, most serious first', () => {
    expect(kindsIn({ typo: 2, amendment: 1, added: 4, substantive: 0 })).toEqual(['amendment', 'added', 'typo'])
    expect(kindsIn({})).toEqual([])
  })

  it('tells a deck change from an amendment', () => {
    expect(recheckLabel('content_changed')).toBe('Updated, please re-check')
    expect(recheckLabel(null)).toBe('Updated, please re-check')
    expect(recheckLabel('amendment')).toBe('Check against the amendment')
    expect(recheckHelp('amendment')).toMatch(/untouched/)
    expect(recheckHelp('content_changed')).toMatch(/sooner/)
  })

  it('reports what an apply did', () => {
    expect(appliedMessage(result({ changed: false }))).toBe('You already have the latest version.')
    expect(appliedMessage(result({ cards_created: 2, cards_reset: 1 }))).toBe(
      'Updated: 2 new cards, 1 card to re-check.',
    )
    expect(appliedMessage(result())).toBe('Updated.')
  })

  it('words what returns today and what the server held back', () => {
    expect(returningText(0)).toBe('')
    expect(returningText(1)).toMatch(/1 card comes back/)
    expect(returningText(4)).toMatch(/4 cards come back/)
    expect(moreText({ more: { typo: 3 } }, 'typo')).toBe('and 3 more')
    expect(moreText({ more: {} }, 'typo')).toBe('')
  })

  it('explains each way a chapter can change', () => {
    expect(relationText('split')).toMatch(/split/)
    expect(relationText('merged')).toMatch(/merged/)
    expect(relationText('none')).toMatch(/no match/)
    expect(relationText('same')).toMatch(/changed/)
  })
})
