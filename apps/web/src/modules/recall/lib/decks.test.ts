import { describe, expect, it } from 'vitest'

import { completeRowCount, csvFileName, jsonFileName } from './dataExport'
import {
  cardsText,
  isTier,
  newerText,
  subscribeMessage,
  subscriptionState,
  tierLabel,
  tiersText,
  tooLargeText,
} from './decks'
import type { ApiDeck, SubscribeResult } from './schemas'
import { activeSection, RECALL_SECTIONS } from './sections'

const deck = (over: Partial<ApiDeck> = {}): ApiDeck => ({
  id: 'd1',
  slug: 's',
  title: 'T',
  description: '',
  course_id: null,
  level_id: null,
  subject_key: null,
  subject_name: null,
  chapter_id: null,
  chapter_name: null,
  version_no: 1,
  item_count: 3,
  card_count: 4,
  tiers: { mandatory: 1, important: 0, bullet: 2 },
  published_at: null,
  changelog_md: '',
  subscription: null,
  ...over,
})

describe('deck words', () => {
  it('counts cards and tiers', () => {
    expect(cardsText(deck({ card_count: 1 }))).toBe('1 card')
    expect(cardsText(deck({ card_count: 4 }))).toBe('4 cards')
    expect(tiersText(deck().tiers)).toBe('1 must know, 2 good to know')
    expect(tiersText({ mandatory: 0, important: 0, bullet: 0 })).toBe('')
  })

  it('shows newer versions as a count only', () => {
    expect(newerText(0)).toBe('')
    expect(newerText(1)).toBe('A newer version exists')
    expect(newerText(3)).toBe('3 newer versions exist')
  })

  it('knows where a deck stands for her', () => {
    expect(subscriptionState(deck())).toBe('none')
    const sub = {
      id: 's',
      status: 'archived' as const,
      version_no: 1,
      newer_versions: 0,
      subscribed_at: 'x',
      min_importance: 'bullet',
    }
    expect(subscriptionState(deck({ subscription: sub }))).toBe('archived')
    expect(subscriptionState(deck({ subscription: { ...sub, status: 'active' } }))).toBe('active')
  })

  it('labels tiers', () => {
    expect(isTier('mandatory')).toBe(true)
    expect(isTier('nope')).toBe(false)
    expect(tierLabel('important')).toBe('Important')
    expect(tierLabel('weird')).toBe('weird')
  })

  it('says what a subscribe did', () => {
    const base = { created: true, cards_created: 5, cards_restored: 0, deck: deck() } satisfies SubscribeResult
    expect(subscribeMessage(base)).toBe('5 cards added to your revision.')
    expect(subscribeMessage({ ...base, cards_created: 1 })).toBe('1 card added to your revision.')
    expect(subscribeMessage({ ...base, cards_created: 0, cards_restored: 2 })).toMatch(
      /2 cards are back with your progress/,
    )
    expect(subscribeMessage({ ...base, created: false })).toBe('You already have this deck.')
  })

  it('explains a deck that is too large', () => {
    const body = { error: { code: 'deck_too_large', extra: { cards: 501, limit: 500 } } }
    expect(tooLargeText(body)).toMatch(/501 cards.*500/)
    expect(tooLargeText({ error: { code: 'deck_too_large' } })).toMatch(/too large/)
    expect(tooLargeText({ error: { code: 'other' } })).toBeNull()
    expect(tooLargeText(undefined)).toBeNull()
  })
})

describe('data export files', () => {
  it('reads the closing line of a CSV', () => {
    expect(completeRowCount('a,b\r\n1,2\r\n#complete,1\r\n')).toBe(1)
    expect(completeRowCount('a\r\n#complete,20000')).toBe(20000)
    expect(completeRowCount('a,b\r\n1,2\r\n')).toBeNull() // cut short
    expect(completeRowCount('a\r\n#next,abc\r\n')).toBeNull()
    expect(completeRowCount('')).toBeNull()
  })

  it('names files with her own date', () => {
    const d = new Date(2026, 9, 9)
    expect(csvFileName('reviews', d)).toBe('recall-reviews-2026-10-09.csv')
    expect(jsonFileName(d)).toBe('recall-data-2026-10-09.json')
  })
})

describe('sections', () => {
  it('has a Decks tab that stays active on a deck page', () => {
    expect(RECALL_SECTIONS.map((s) => s.value)).toContain('decks')
    expect(activeSection('/app/recall/decks', RECALL_SECTIONS)).toBe('decks')
    expect(activeSection('/app/recall/decks/abc', RECALL_SECTIONS)).toBe('decks')
  })
})
