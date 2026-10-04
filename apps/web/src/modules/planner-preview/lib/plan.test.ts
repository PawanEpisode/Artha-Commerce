import { describe, expect, it } from 'vitest'
import { buildPlan } from './plan'

describe('buildPlan', () => {
  const subjects = ['A', 'B', 'C', 'D']

  it('allocates one rest day a week', () => {
    expect(buildPlan({ subjects, months: 1, hoursPerDay: 5 }).studyDays).toBe(26)
  })

  it('splits hours evenly across subjects', () => {
    const plan = buildPlan({ subjects, months: 6, hoursPerDay: 4 })
    expect(new Set(plan.perSubject.map((s) => s.hours)).size).toBe(1)
  })

  it('phase shares add up to roughly the total', () => {
    const plan = buildPlan({ subjects, months: 6, hoursPerDay: 5 })
    const sum = plan.phases.reduce((n, p) => n + p.hours, 0)
    expect(Math.abs(sum - plan.totalHours)).toBeLessThanOrEqual(1)
  })

  it('handles an empty subject list', () => {
    expect(buildPlan({ subjects: [], months: 3, hoursPerDay: 3 }).perSubject).toEqual([])
  })
})
