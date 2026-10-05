import { describe, expect, it } from 'vitest'

import {
  firstBlocking,
  firstTodo,
  nextAfter,
  previousBefore,
  resolveStep,
  type StepInfo,
  type StepStateName,
  walkOf,
} from './onboardingSteps'

const step = (key: string, state: StepStateName, mandatory = true, available = true): StepInfo => ({
  key,
  state,
  mandatory,
  available,
})

const fresh = [
  step('profile', 'todo'),
  step('course', 'todo'),
  step('hours', 'todo'),
  step('targets', 'todo'),
  step('catchup', 'todo', false),
  step('avatar', 'todo', false),
]

describe('walkOf', () => {
  it('a new student walks every available step in order', () => {
    expect(walkOf('full', fresh)).toEqual(['profile', 'course', 'hours', 'targets', 'catchup', 'avatar'])
  })
  it('leaves out unavailable steps (the targets flag is off)', () => {
    const steps = fresh.map((s) =>
      s.key === 'targets' ? { ...s, state: 'unavailable' as const, available: false } : s,
    )
    expect(walkOf('full', steps)).not.toContain('targets')
  })
  it('a returning student only walks the mandatory steps still to do', () => {
    const steps = fresh.map((s) => (['course'].includes(s.key) ? { ...s, state: 'done' as const } : s))
    expect(walkOf('update', steps)).toEqual(['profile', 'hours', 'targets'])
  })
  it('ignores steps the web has no screen for', () => {
    expect(walkOf('full', [...fresh, step('coaching', 'todo', false)])).not.toContain('coaching')
  })
})

describe('resolveStep', () => {
  const walk = walkOf('full', fresh)
  it('opens the first step to do when none is asked for', () => {
    expect(resolveStep(walk, fresh, undefined)).toEqual({ key: 'profile', redirected: false })
  })
  it('allows going back to a finished step and up to the first missing mandatory one', () => {
    const steps = fresh.map((s) => (s.key === 'profile' || s.key === 'course' ? { ...s, state: 'done' as const } : s))
    expect(resolveStep(walk, steps, 'course').key).toBe('course')
    expect(resolveStep(walk, steps, 'hours').key).toBe('hours')
  })
  it('does not let the URL skip a missing mandatory step', () => {
    expect(resolveStep(walk, fresh, 'targets')).toEqual({ key: 'profile', redirected: true })
    expect(resolveStep(walk, fresh, 'avatar').key).toBe('profile')
  })
  it('an unknown step falls back to the right one', () => {
    expect(resolveStep(walk, fresh, 'nope')).toEqual({ key: 'profile', redirected: true })
  })
  it('after the mandatory steps it offers optional ones, then nothing', () => {
    const mandatoryDone = fresh.map((s) => (s.mandatory ? { ...s, state: 'done' as const } : s))
    expect(resolveStep(walk, mandatoryDone, undefined).key).toBe('catchup')
    expect(resolveStep(walk, mandatoryDone, 'avatar').key).toBe('avatar')
    const allDone = mandatoryDone.map((s) => ({ ...s, state: s.mandatory ? ('done' as const) : ('skipped' as const) }))
    expect(resolveStep(walk, allDone, undefined).key).toBeNull()
  })
})

describe('helpers', () => {
  const walk = ['profile', 'course', 'hours']
  it('finds neighbours', () => {
    expect(nextAfter(walk, 'profile')).toBe('course')
    expect(nextAfter(walk, 'hours')).toBeNull()
    expect(previousBefore(walk, 'course')).toBe('profile')
    expect(previousBefore(walk, 'profile')).toBeNull()
  })
  it('first blocking and first todo', () => {
    expect(firstBlocking(walk, fresh)).toBe('profile')
    expect(firstTodo(['catchup'], fresh)).toBe('catchup')
    expect(firstBlocking(['catchup'], fresh)).toBeNull()
  })
})
