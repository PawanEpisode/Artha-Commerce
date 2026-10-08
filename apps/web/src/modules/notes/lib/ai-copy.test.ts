import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import {
  allowanceText,
  dropNote,
  failureText,
  startFailureText,
  summaryAllowance,
  withoutSourcesSection,
} from './ai-copy'
import { classifyAiError } from './ai-errors'

const err = (status: number, code: string, details?: unknown) =>
  new ApiError(status, 'x', { error: { code, message: 'm', details } })
const usage = (used: number, limit: number) =>
  ({ limits: { ai_summaries_per_month: limit }, used: { ai_summaries: used }, resets_on: '2026-11-01' }) as never

describe('classifyAiError', () => {
  it('maps each refusal to a reason the screen can branch on', () => {
    expect(classifyAiError(err(403, 'ai_not_consented', { version: 'v1' }))).toEqual({
      reason: 'not_consented',
      version: 'v1',
    })
    expect(classifyAiError(err(503, 'ai_unavailable')).reason).toBe('unavailable')
    expect(classifyAiError(err(503, 'ai_budget_exhausted')).reason).toBe('budget')
    expect(classifyAiError(err(403, 'feature_disabled')).reason).toBe('feature_off')
    expect(
      classifyAiError(err(422, 'not_enough_material', { items: 1, chars: 10, min_items: 3, min_chars: 400 })),
    ).toMatchObject({
      reason: 'not_enough',
    })
    expect(classifyAiError(err(429, 'quota_exceeded', { used: 5, limit: 5, resets_on: '2026-11-01' }))).toEqual({
      reason: 'quota',
      used: 5,
      limit: 5,
      resetsOn: '2026-11-01',
    })
  })

  it('never throws on anything else', () => {
    expect(classifyAiError(new Error('boom')).reason).toBe('other')
    expect(classifyAiError(undefined).reason).toBe('other')
  })
})

describe('summary copy', () => {
  it('words the allowance for no plan, none left and some left', () => {
    expect(allowanceText(summaryAllowance(usage(0, 0)))).toMatch(/not part of your plan/)
    expect(allowanceText(summaryAllowance(usage(5, 5)))).toMatch(/used all 5/)
    expect(allowanceText(summaryAllowance(usage(2, 5)))).toBe('Uses 1 of your 3 remaining summaries this month.')
    expect(allowanceText(summaryAllowance(undefined))).toBe('')
  })

  it('always says nothing was charged when a request failed', () => {
    for (const code of ['model_error', 'blocked', 'too_little', 'unavailable', null] as const) {
      expect(failureText(code)).toMatch(/Nothing was used/)
    }
  })

  it('explains a refusal to start in plain words', () => {
    expect(startFailureText({ reason: 'budget' })).toMatch(/busy for today/)
    expect(startFailureText({ reason: 'other' })).toMatch(/try again/)
  })

  it('hides only the trailing Sources section', () => {
    expect(withoutSourcesSection('# A\n\n- x [1]\n\n## Sources\n1. a')).toBe('# A\n\n- x [1]\n')
    expect(withoutSourcesSection('# A')).toBe('# A')
  })

  it('says nothing when no point was dropped', () => {
    expect(dropNote(0)).toBe('')
    expect(dropNote(1)).toMatch(/1 point/)
  })
})
