import { describe, expect, it } from 'vitest'

import {
  explicitDeepLink,
  LAST_VISIT_MAX_AGE_MS,
  onboardingPath,
  resolvePostAuthDestination,
  restorableLastVisit,
} from './destination'
import type { Bootstrap } from './types'

const NOW = new Date('2026-10-06T10:00:00Z')
const ago = (ms: number) => new Date(NOW.getTime() - ms).toISOString()
const facts = (status: Bootstrap['onboarding']['status'], visit: Bootstrap['last_visit'] = null) => ({
  onboarding: {
    status,
    mode: 'full' as const,
    required_version: 2,
    completed_version: status === 'completed' ? 2 : 0,
    next_step: null,
    missing: [],
  },
  last_visit: visit,
})
const visit = (path: string, at: string | null, search = '') => ({ path, search, at })
const yes = () => true
const options = { now: NOW, isRestorable: yes }

describe('explicitDeepLink', () => {
  it('keeps real same-site targets', () => {
    expect(explicitDeepLink('/app/syllabus/x/y')).toBe('/app/syllabus/x/y')
    expect(explicitDeepLink('/courses/cma?all=1')).toBe('/courses/cma?all=1')
  })
  it.each([
    undefined,
    null,
    '',
    '/app',
    'https://evil.com',
    '//evil.com',
    '/\\evil',
    '/app/onboarding',
    '/app/onboarding?step=hours',
    '/login',
    '/login?next=/app/notes/trash',
    '/signup',
    '/auth/callback',
  ])('ignores %j', (value) => expect(explicitDeepLink(value)).toBeNull())
})

describe('onboardingPath', () => {
  it('carries a deep link and drops everything else', () => {
    expect(onboardingPath('/app/tracker')).toBe('/app/onboarding?next=%2Fapp%2Ftracker')
    expect(onboardingPath('https://evil.com')).toBe('/app/onboarding')
    expect(onboardingPath()).toBe('/app/onboarding')
  })
})

describe('restorableLastVisit', () => {
  it('needs the allow-list, a time and an age under 14 days', () => {
    const f = facts('completed', visit('/app/syllabus/a/b', ago(1000), '?x=1'))
    expect(restorableLastVisit(f, options)).toBe('/app/syllabus/a/b?x=1')
    expect(restorableLastVisit(f, { now: NOW })).toBeNull()
    expect(restorableLastVisit(f, { now: NOW, isRestorable: () => false })).toBeNull()
    expect(restorableLastVisit(facts('completed', visit('/app/x', ago(LAST_VISIT_MAX_AGE_MS + 1))), options)).toBeNull()
    expect(restorableLastVisit(facts('completed', visit('/app/x', ago(LAST_VISIT_MAX_AGE_MS))), options)).toBe('/app/x')
  })
  it('ignores a missing, undated, future or unsafe visit', () => {
    expect(restorableLastVisit(facts('completed'), options)).toBeNull()
    expect(restorableLastVisit(facts('completed', visit('/app/x', null)), options)).toBeNull()
    expect(restorableLastVisit(facts('completed', visit('/app/x', 'garbage')), options)).toBeNull()
    expect(restorableLastVisit(facts('completed', visit('/app/x', ago(-60_000))), options)).toBeNull()
    expect(restorableLastVisit(facts('completed', visit('//evil.com', ago(1000))), options)).toBeNull()
  })
})

describe('resolvePostAuthDestination', () => {
  const recent = visit('/app/tracker', ago(3600_000))

  it('sends an unfinished student to onboarding, whatever else is set', () => {
    for (const status of ['not_started', 'in_progress'] as const) {
      expect(resolvePostAuthDestination(facts(status, recent), '/app/focus', options)).toBe(
        '/app/onboarding?next=%2Fapp%2Ffocus',
      )
    }
    expect(resolvePostAuthDestination(facts('not_started'), undefined, options)).toBe('/app/onboarding')
  })
  it('prefers the deep link, then the last visit, then /app', () => {
    const done = facts('completed', recent)
    expect(resolvePostAuthDestination(done, '/app/focus', options)).toBe('/app/focus')
    expect(resolvePostAuthDestination(done, undefined, options)).toBe('/app/tracker')
    expect(resolvePostAuthDestination(done, '/app', options)).toBe('/app/tracker')
    expect(resolvePostAuthDestination(facts('completed'), undefined, options)).toBe('/app')
  })
  it('never follows an unsafe next', () => {
    expect(resolvePostAuthDestination(facts('completed'), 'https://evil.com', options)).toBe('/app')
  })
})
