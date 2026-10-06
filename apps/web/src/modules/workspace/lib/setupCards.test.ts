import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { dismiss, readDismissed, skippedSteps } from './setupCards'

const step = (key: string, state: string, over = {}) =>
  ({ key, state, mandatory: false, available: true, ...over }) as never

describe('skippedSteps', () => {
  it('lists skipped optional steps that are available and not dismissed', () => {
    const state = {
      steps: [
        step('avatar', 'skipped'),
        step('catchup', 'skipped', { available: false }),
        step('targets', 'skipped', { mandatory: true }),
        step('hours', 'done'),
        step('course', 'todo'),
        step('extra', 'skipped'),
      ],
    }
    expect(skippedSteps(state, ['extra'])).toEqual(['avatar'])
    expect(skippedSteps(state, [])).toEqual(['avatar', 'extra'])
  })
})

describe('alerts card', () => {
  it('is offered to a student who has not seen the step (added after they finished onboarding)', () => {
    const state = { steps: [step('alerts', 'todo'), step('avatar', 'todo')] }
    expect(skippedSteps(state, [])).toEqual(['alerts'])
  })
  it('goes away once the step is done, unavailable or hidden', () => {
    expect(skippedSteps({ steps: [step('alerts', 'done')] }, [])).toEqual([])
    expect(skippedSteps({ steps: [step('alerts', 'todo', { available: false })] }, [])).toEqual([])
    expect(skippedSteps({ steps: [step('alerts', 'todo')] }, ['alerts'])).toEqual([])
  })
})

describe('dismissal storage', () => {
  beforeEach(() => {
    const store = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('remembers per user without duplicates', () => {
    expect(readDismissed('u1')).toEqual([])
    dismiss('u1', 'avatar')
    expect(dismiss('u1', 'avatar')).toEqual(['avatar'])
    expect(readDismissed('u2')).toEqual([])
  })
  it('ignores a broken value', () => {
    localStorage.setItem('setup-cards-dismissed:u1', '{oops')
    expect(readDismissed('u1')).toEqual([])
    localStorage.setItem('setup-cards-dismissed:u1', '[1,"a"]')
    expect(readDismissed('u1')).toEqual(['a'])
  })
})
