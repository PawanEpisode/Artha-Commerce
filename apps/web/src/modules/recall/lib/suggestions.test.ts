import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import type { AiOverview, SuggestionBatch } from './schemas'
import {
  batchSummary,
  canAsk,
  decidedText,
  failedText,
  fieldLabel,
  isActive,
  maxCount,
  pollInterval,
  quotaText,
  requestProblem,
  suggestionFailure,
} from './suggestions'

const overview = (over: Partial<AiOverview> = {}): AiOverview => ({
  available: true,
  consent: { version: 'v1', given: true, given_at: null },
  quota: { batches_used: 0, batches_limit: 3, suggestions_used: 0, suggestions_limit: 30, resets_on: '2026-10-13' },
  sources: ['notes', 'pasted'],
  limits: { min_count: 1, max_count: 10, default_count: 5, max_pasted_chars: 12000, min_source_chars: 80 },
  waiting_drafts: 0,
  ...over,
})

const batch = (over: Partial<SuggestionBatch> = {}): SuggestionBatch => ({
  id: 'b1',
  status: 'ready',
  chapter_id: 'c1',
  sources: ['notes'],
  kinds: [],
  requested_count: 5,
  produced: 3,
  dropped: 0,
  error_code: null,
  created_at: '2026-10-12T00:00:00Z',
  finished_at: null,
  expires_at: null,
  suggestions: [],
  ...over,
})

describe('polling', () => {
  it('reads often at first, then calmly, and stops when the batch is finished', () => {
    expect(pollInterval(batch({ status: 'running' }), 1_000)).toBe(2_000)
    expect(pollInterval(batch({ status: 'queued' }), 60_000)).toBe(4_000)
    expect(pollInterval(batch({ status: 'ready' }), 0)).toBeNull()
    expect(pollInterval(undefined, 0)).toBeNull()
    expect(isActive(batch({ status: 'failed' }))).toBe(false)
  })
})

describe('the allowance', () => {
  it('says what is left, and when it is gone', () => {
    expect(quotaText(overview().quota)).toBe('Today you can ask 3 more times for up to 30 suggestions.')
    expect(quotaText({ ...overview().quota, batches_used: 3 })).toMatch(/all of today’s requests/)
    expect(quotaText({ ...overview().quota, suggestions_used: 30 })).toMatch(/all of today’s suggestions/)
  })

  it('does not let the stepper pass what is left of the day', () => {
    expect(maxCount(overview())).toBe(10)
    expect(maxCount(overview({ quota: { ...overview().quota, suggestions_used: 27 } }))).toBe(3)
    expect(canAsk(overview().quota, 31)).toBe(false)
  })
})

describe('requestProblem', () => {
  const ok = { chapterId: 'c1', sources: ['notes' as const], pasted: '', count: 5 }
  it('is null when the request is ready', () => expect(requestProblem(ok, overview())).toBeNull())
  it('asks for a chapter, then a source, then enough pasted text', () => {
    expect(requestProblem({ ...ok, chapterId: null }, overview())).toBe('Choose a chapter first.')
    expect(requestProblem({ ...ok, sources: [] }, overview())).toMatch(/where the cards should come from/)
    expect(requestProblem({ ...ok, sources: ['pasted'], pasted: 'short' }, overview())).toMatch(/at least 80/)
    expect(requestProblem({ ...ok, sources: ['notes', 'pasted'], pasted: '' }, overview())).toBeNull()
  })
  it('explains a spent allowance instead of a dead button', () => {
    const spent = overview({ quota: { ...overview().quota, batches_used: 3 } })
    expect(requestProblem(ok, spent)).toMatch(/used all of today/)
  })
})

describe('what the screen says about a batch', () => {
  it('counts the ready suggestions and the ones the checker left out', () => {
    expect(batchSummary(batch({ produced: 1 }))).toBe('1 suggestion ready.')
    expect(batchSummary(batch({ produced: 4, dropped: 2 }))).toBe(
      '4 suggestions ready. 2 drafts were left out because their quote was not in your material.',
    )
    expect(batchSummary(batch({ status: 'running' }))).toMatch(/Reading/)
  })
  it('says a failure was free', () => {
    for (const code of ['nothing_usable', 'blocked', 'too_little', 'unavailable', 'other'])
      if (code !== 'other') expect(failedText({ error_code: code })).toMatch(/not charged/)
    expect(failedText({ error_code: 'weird' })).toMatch(/Try again/)
  })
  it('labels decisions and fields', () => {
    expect(decidedText({ status: 'edited_accepted' })).toBe('Added to your cards')
    expect(decidedText({ status: 'draft' })).toBeNull()
    expect(fieldLabel('case_name')).toBe('Case name')
    expect(fieldLabel('prompt_md')).toBe('Prompt')
  })
})

describe('suggestionFailure', () => {
  const err = (status: number, code?: string) => new ApiError(status, 'failed', code ? { error: { code } } : {})
  it('uses a sentence per known code and a calm default', () => {
    expect(suggestionFailure(err(403, 'ai_not_consented'))).toMatch(/Agree/)
    expect(suggestionFailure(err(429, 'quota_exceeded'))).toMatch(/allowance/)
    expect(suggestionFailure(err(429))).toMatch(/Too many/)
    expect(suggestionFailure(err(0))).toMatch(/offline/)
    expect(suggestionFailure(new Error('x'))).toBe('Something went wrong. Please try again.')
  })
})
