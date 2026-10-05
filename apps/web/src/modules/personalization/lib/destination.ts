/**
 * The one decision function for "where does this student go now" (PRD 5.1). Pure, so every caller (sign-in
 * containers, the guard, the landing redirect) agrees. Order of precedence is fixed:
 * onboarding gate, then explicit deep link, then last visit, then the workspace.
 */
import { DEFAULT_AFTER_LOGIN, safeNextPath } from '~/modules/auth'

import type { Bootstrap } from './types'

export const ONBOARDING_PATH = '/app/onboarding'
/** A last visit older than this is stale: the student probably wants a fresh start. */
export const LAST_VISIT_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000

export type DestinationFacts = Pick<Bootstrap, 'onboarding' | 'last_visit'>

export interface DestinationOptions {
  now?: Date
  /** Allow-list of pages worth coming back to. Without it, the last visit is never restored. */
  isRestorable?: (target: string) => boolean
}

export const isOnboardingComplete = (facts: Pick<Bootstrap, 'onboarding'>) => facts.onboarding.status === 'completed'

/** `next` when it is a real deep link: same-site, not the default landing, not the onboarding page itself. */
export function explicitDeepLink(next: unknown): string | null {
  const safe = safeNextPath(next, '')
  if (!safe || safe === DEFAULT_AFTER_LOGIN || safe.split(/[?#]/)[0] === ONBOARDING_PATH) return null
  return safe
}

/** `/app/onboarding`, carrying the deep link along so it survives the flow. */
export function onboardingPath(next?: unknown): string {
  const link = explicitDeepLink(next)
  return link ? `${ONBOARDING_PATH}?next=${encodeURIComponent(link)}` : ONBOARDING_PATH
}

export function restorableLastVisit(facts: DestinationFacts, options: DestinationOptions = {}): string | null {
  const { last_visit: visit } = facts
  const { now = new Date(), isRestorable } = options
  if (!visit || !visit.at || !isRestorable) return null
  const age = now.getTime() - Date.parse(visit.at)
  if (!Number.isFinite(age) || age < 0 || age > LAST_VISIT_MAX_AGE_MS) return null
  const target = `${visit.path}${visit.search}`
  return safeNextPath(target, '') && isRestorable(target) ? target : null
}

export function resolvePostAuthDestination(
  facts: DestinationFacts,
  next?: unknown,
  options: DestinationOptions = {},
): string {
  if (!isOnboardingComplete(facts)) return onboardingPath(next)
  return explicitDeepLink(next) ?? restorableLastVisit(facts, options) ?? DEFAULT_AFTER_LOGIN
}
