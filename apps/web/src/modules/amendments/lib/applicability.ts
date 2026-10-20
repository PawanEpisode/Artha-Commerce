import type { ApplicabilityResult, DocumentTermRule } from './types'

/**
 * Pure decision function implementing PRD Section 5.3 in TypeScript:
 * Evaluates whether an amendment card applies to a student's attempt.
 * Twin of apps/api/modules/amendments/domain/applicability.py.
 */
export function evaluateApplicability(
  studentTerm: string | null | undefined,
  documentTerms: DocumentTermRule[],
  cardEffectiveTerm?: string | null,
): ApplicabilityResult {
  if (!studentTerm) {
    return {
      status: 'unknown',
      reason_code: 'no_target_term',
      reason_text: 'Please set your target exam attempt to see applicability.',
    }
  }

  const exactRule = documentTerms.find((t) => t.term_code === studentTerm)

  if (exactRule) {
    if (exactRule.applicability === 'excluded') {
      return {
        status: 'not_applicable',
        reason_code: 'explicitly_excluded',
        reason_text: 'The Institute explicitly excludes this attempt from this amendment.',
      }
    }

    if (cardEffectiveTerm && studentTerm < cardEffectiveTerm) {
      return {
        status: 'not_applicable',
        reason_code: 'effective_later',
        reason_text: `Takes effect from attempt ${cardEffectiveTerm} onwards.`,
      }
    }

    return {
      status: 'applies',
      reason_code: 'declared_term',
      reason_text: `Officially applicable for attempt ${studentTerm}.`,
    }
  }

  const applicableTerms = documentTerms.filter((t) => t.applicability === 'applies')

  if (applicableTerms.length === 0) {
    return {
      status: 'unknown',
      reason_code: 'no_term_declared',
      reason_text: 'The Institute has not declared applicable terms for this document yet.',
    }
  }

  const minDeclared = applicableTerms.map((t) => t.term_code).sort()[0]

  if (minDeclared && studentTerm < minDeclared) {
    return {
      status: 'not_applicable',
      reason_code: 'for_later_attempt',
      reason_text: `Meant for later attempts (starting from ${minDeclared}).`,
    }
  }

  return {
    status: 'unknown',
    reason_code: 'rule_not_published',
    reason_text: 'The Institute has not published the amendments rule for your attempt yet.',
  }
}
