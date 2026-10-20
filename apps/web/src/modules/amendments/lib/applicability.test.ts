import { describe, expect, it } from 'vitest'

import { evaluateApplicability } from './applicability'
import type { DocumentTermRule } from './types'

describe('evaluateApplicability (TypeScript twin of domain/applicability.py)', () => {
  it('returns unknown when student term is missing', () => {
    const res = evaluateApplicability(null, [])
    expect(res.status).toBe('unknown')
    expect(res.reason_code).toBe('no_target_term')
  })

  it('returns applies when exact term is declared', () => {
    const terms: DocumentTermRule[] = [{ term_code: '2027-05', applicability: 'applies', cutoff_date: '2026-10-31' }]
    const res = evaluateApplicability('2027-05', terms)
    expect(res.status).toBe('applies')
    expect(res.reason_code).toBe('declared_term')
  })

  it('returns not_applicable when exact term is explicitly excluded', () => {
    const terms: DocumentTermRule[] = [{ term_code: '2027-05', applicability: 'excluded', cutoff_date: null }]
    const res = evaluateApplicability('2027-05', terms)
    expect(res.status).toBe('not_applicable')
    expect(res.reason_code).toBe('explicitly_excluded')
  })

  it('returns not_applicable when card takes effect from later attempt', () => {
    const terms: DocumentTermRule[] = [{ term_code: '2026-11', applicability: 'applies', cutoff_date: null }]
    const res = evaluateApplicability('2026-11', terms, '2027-05')
    expect(res.status).toBe('not_applicable')
    expect(res.reason_code).toBe('effective_later')
  })

  it('returns not_applicable when student attempt is earlier than min declared term', () => {
    const terms: DocumentTermRule[] = [{ term_code: '2027-05', applicability: 'applies', cutoff_date: null }]
    const res = evaluateApplicability('2026-11', terms)
    expect(res.status).toBe('not_applicable')
    expect(res.reason_code).toBe('for_later_attempt')
  })

  it('returns unknown when student attempt is later than declared terms', () => {
    const terms: DocumentTermRule[] = [{ term_code: '2026-11', applicability: 'applies', cutoff_date: null }]
    const res = evaluateApplicability('2027-05', terms)
    expect(res.status).toBe('unknown')
    expect(res.reason_code).toBe('rule_not_published')
  })
})
