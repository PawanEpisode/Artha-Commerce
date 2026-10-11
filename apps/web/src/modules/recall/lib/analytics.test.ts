import { describe, expect, it, vi } from 'vitest'

const track = vi.hoisted(() => vi.fn())
vi.mock('~/modules/observability', () => ({ track }))

import { ALLOWED, allowedProperties, cleanProperties, type RecallEvent, trackRecall } from './analytics'

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
      'recall_quick_planned',
      'recall_quick_started',
      'recall_quick_completed',
      'recall_cram_started',
      'recall_pacing_viewed',
    ] as RecallEvent[]
    for (const e of events) {
      for (const key of allowedProperties(e))
        expect(key).not.toMatch(/text|front|back|md|note|name|title|email|token|answer|question/)
    }
  })
})

describe('recall analytics privacy gate', () => {
  it('has exactly the events and properties reviewed for privacy: adding one needs this list changed on purpose', () => {
    expect(Object.fromEntries(Object.entries(ALLOWED).map(([event, keys]) => [event, [...keys].sort()]))).toEqual({
      recall_card_viewed: ['first', 'kind', 'state'],
      recall_catchup_cleared: ['days_taken'],
      recall_catchup_started: ['due_total', 'overdue_days_max', 'queue_size'],
      recall_leech_action: ['action', 'lapses'],
      recall_leech_shown: ['lapses'],
      recall_pack_downloaded: ['bytes_bucket', 'cards'],
      recall_cram_started: ['set_size'],
      recall_pacing_viewed: ['days_to_exam', 'feasible', 'needed_per_day'],
      recall_quick_completed: ['reviewed', 'set_size'],
      recall_quick_planned: ['cut_off', 'days_to_exam', 'minutes_per_day', 'set_size'],
      recall_quick_started: ['set_size'],
      recall_rebalance_used: ['days', 'moved'],
      recall_review_undone: ['within_seconds'],
      recall_session_started: ['first', 'mode', 'offline', 'planned', 'source'],
      recall_settings_changed: ['changed_keys', 'retention'],
      recall_sync_completed: ['dropped_deleted', 'dropped_stale', 'duration_ms', 'events', 'merged'],
    })
  })

  it('lets no card text, deck title or id through under any allowed property of any event', () => {
    const leaks = [
      'What is the time limit for ITC under section 16(4)?',
      'Companies Act 2013 deck',
      'Section 17(5)',
      '3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11',
      '3f2b8c7e6d2e4f0e9a450f9e5b3e1c11',
      'a'.repeat(33),
      '<script>alert(1)</script>',
      { id: '3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11' },
      ['gst'],
      null,
      undefined,
    ]
    for (const event of Object.keys(ALLOWED) as RecallEvent[]) {
      for (const key of allowedProperties(event)) {
        for (const leak of leaks) {
          expect(cleanProperties(event, { [key]: leak }), `${event}.${String(key)}`).toEqual({})
        }
      }
      expect(cleanProperties(event, { card_id: 'x', deck_id: 'x', title: 'x', front_md: 'x', note: 'x' })).toEqual({})
    }
  })

  // The call sites are read from the source: a new `trackRecall` call, or a new property in one, fails here until it is reviewed.
  const sources = import.meta.glob('../**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true }) as Record<
    string,
    string
  >
  const files = Object.entries(sources).filter(([path]) => !/\.test\.tsx?$/.test(path) && path !== './analytics.ts')

  const callsOf = (source: string) => {
    const calls: { event: string; entries: { key: string; value: string }[] }[] = []
    for (const match of source.matchAll(/trackRecall\(\s*'([a-z_]+)'\s*(?:,\s*\{)?/g)) {
      const event = match[1]
      let i = match.index + match[0].length
      const entries: { key: string; value: string }[] = []
      if (match[0].endsWith('{')) {
        let depth = 1
        let start = i
        const parts: string[] = []
        for (; i < source.length && depth > 0; i++) {
          const ch = source[i]
          if (ch === '{' || ch === '(' || ch === '[') depth++
          else if (ch === '}' || ch === ')' || ch === ']') depth--
          if ((ch === ',' && depth === 1) || depth === 0) {
            parts.push(source.slice(start, i))
            start = i + 1
          }
        }
        for (const part of parts.map((p) => p.trim()).filter(Boolean)) {
          const colon = part.indexOf(':')
          entries.push(
            colon < 0 ? { key: part, value: part } : { key: part.slice(0, colon).trim(), value: part.slice(colon + 1) },
          )
        }
      }
      calls.push({ event, entries })
    }
    return calls
  }

  it('finds the call sites it is meant to check', () => {
    const all = files.flatMap(([, source]) => callsOf(source))
    expect(all.length).toBeGreaterThanOrEqual(8)
  })

  it('only tracks listed events, with listed properties, and never a text, title or id expression', () => {
    const problems: string[] = []
    for (const [path, source] of files) {
      for (const { event, entries } of callsOf(source)) {
        const allowed: readonly string[] | undefined = (ALLOWED as Record<string, readonly string[]>)[event]
        if (!allowed) problems.push(`${path}: unlisted event ${event}`)
        for (const { key, value } of entries) {
          if (allowed && !allowed.includes(key)) problems.push(`${path}: ${event} sends unlisted property ${key}`)
          if (/front_md|back_md|fields|title|prompt|answer|note|name|text|\.id\b|[a-z]Id\b|_id\b/.test(value))
            problems.push(`${path}: ${event}.${key} looks like content or an id (${value.trim().slice(0, 40)})`)
        }
      }
    }
    expect(problems).toEqual([])
  })

  it('keeps every other recall file away from PostHog: only lib/analytics.ts may import track or posthog', () => {
    const direct = files
      .filter(([, source]) =>
        /import[^;]*\b(track|posthog)\b[^;]*from '(~\/modules\/observability|posthog-js)'/.test(source),
      )
      .map(([path]) => path)
    expect(direct).toEqual([])
  })
})
