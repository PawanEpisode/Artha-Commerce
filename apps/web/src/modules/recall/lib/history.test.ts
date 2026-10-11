import { describe, expect, it } from 'vitest'

import {
  attestationText,
  changeKindLabel,
  countsText,
  resetReasonLabel,
  triggerLabel,
  versionStatus,
  versionsText,
  waitingText,
} from './history'
import type { CardVersionRow } from './schemas'

const v = (over: Partial<CardVersionRow> = {}): CardVersionRow => ({
  version_no: 1,
  change_kind: 'create',
  change_note: '',
  at: null,
  text: '',
  received: true,
  current: false,
  ...over,
})
describe('the words of the update history', () => {
  it('names each kind of change and falls back for an unknown one', () => {
    expect(changeKindLabel('substantive')).toBe('Meaning changed')
    expect(changeKindLabel('amendment')).toBe('Changed after a law amendment')
    expect(changeKindLabel('something_new')).toBe('Changed')
  })

  it('says why a card came back, and has a calm fallback', () => {
    expect(resetReasonLabel('amendment')).toBe('A law this card relies on was amended')
    expect(resetReasonLabel('zzz')).toBe('The card was updated')
  })

  it('says who applied an update', () => {
    expect(triggerLabel('manual')).toBe('You applied it')
    expect(triggerLabel('auto')).toBe('Applied for you')
  })

  it('shows the versions, with the ones in between only when there were some', () => {
    const base = { from_version_no: 2, to_version_no: 3 }
    expect(versionsText({ ...base, versions_skipped: 0 })).toBe('Version 2 to version 3')
    expect(versionsText({ from_version_no: 1, to_version_no: 4, versions_skipped: 1 })).toBe(
      'Version 1 to version 4 (1 version in between)',
    )
    expect(versionsText({ from_version_no: 1, to_version_no: 5, versions_skipped: 3 })).toContain(
      '3 versions in between',
    )
  })

  it('sums up what an update did to her cards in a sentence', () => {
    expect(countsText({ cards_created: 1, rechecked: 2, silent: 1, cards_archived: 3, cards_restored: 1 })).toBe(
      '1 new card, 1 card brought back, 2 cards to re-check, 1 card reworded, 3 cards removed.',
    )
    expect(countsText({})).toBe('None of your cards changed.')
    expect(countsText({ added: 4, removed: 0 })).toBe('None of your cards changed.')
  })

  it('tells her which version she is on and which are waiting', () => {
    expect(versionStatus(v({ current: true }))).toBe('Your card shows this version')
    expect(versionStatus(v({ received: true }))).toBe('An earlier version')
    expect(versionStatus(v({ received: false }))).toBe('Not applied yet')
    expect(waitingText(0)).toBe('')
    expect(waitingText(1)).toBe('1 newer version of this card is waiting in the deck. Apply the update to get it.')
    expect(waitingText(2)).toContain('2 newer versions of this card are waiting')
  })

  it('words the own-words statement for both states', () => {
    expect(attestationText(false).title).toBe('Are these your own words?')
    expect(attestationText(true).title).toBe('You said these are your own words')
    expect(attestationText(true).help).toMatch(/take that back/)
  })
})
