import { describe, expect, it, vi } from 'vitest'

const track = vi.hoisted(() => vi.fn())
vi.mock('~/modules/observability', () => ({ track }))

import { allowedProperties, cleanProperties, type RecallEvent, trackRecall } from './analytics'

describe('recall analytics allow-list', () => {
  it('drops properties that are not on the event list', () => {
    expect(cleanProperties('recall_review_undone', { within_seconds: 4, front_md: 'secret', card_id: 'abc' })).toEqual({
      within_seconds: 4,
    })
  })

  it('drops free text even under an allowed name', () => {
    expect(cleanProperties('recall_leech_action', { action: 'Why is the sky blue?', lapses: 9 })).toEqual({ lapses: 9 })
    expect(cleanProperties('recall_leech_action', { action: 'suspend', lapses: 9 })).toEqual({
      action: 'suspend',
      lapses: 9,
    })
    expect(cleanProperties('recall_card_viewed', { kind: 'x'.repeat(40) })).toEqual({})
  })

  it('keeps booleans and finite numbers, drops the rest', () => {
    expect(
      cleanProperties('recall_session_started', {
        offline: true,
        planned: 12,
        mode: null,
        source: 'today',
        first: Number.NaN,
      }),
    ).toEqual({
      offline: true,
      planned: 12,
      source: 'today',
    })
  })

  it('sends only cleaned properties to PostHog', () => {
    trackRecall('recall_session_started', { source: 'today', planned: 5, front_md: 'Section 80C allows ...' })
    expect(track).toHaveBeenCalledWith('recall_session_started', { source: 'today', planned: 5 })
  })

  it('no event can carry a property that looks like content', () => {
    const events = [
      'recall_session_started',
      'recall_card_viewed',
      'recall_review_undone',
      'recall_catchup_started',
      'recall_catchup_cleared',
      'recall_rebalance_used',
      'recall_leech_shown',
      'recall_leech_action',
      'recall_sync_completed',
      'recall_settings_changed',
      'recall_pack_downloaded',
    ] as RecallEvent[]
    for (const e of events) {
      for (const key of allowedProperties(e))
        expect(key).not.toMatch(/text|front|back|md|note|name|title|email|token|answer|question/)
    }
  })
})
