import { describe, expect, it } from 'vitest'

import { type GoalsDraft, validateGoals } from './goalsForm'

const draft = (patch: Partial<GoalsDraft> = {}): GoalsDraft => ({ daily: 120, weekly: 840, subjects: [], ...patch })

describe('validateGoals', () => {
  it('keeps minutes as the payload unit', () => {
    const { entries, errors } = validateGoals(draft({ subjects: [{ key: 'a', subject_id: 's1', minutes: 300 }] }))
    expect(errors).toEqual({})
    expect(entries).toEqual([
      { period: 'daily', subject_id: null, target_minutes: 120 },
      { period: 'weekly', subject_id: null, target_minutes: 840 },
      { period: 'weekly', subject_id: 's1', target_minutes: 300 },
    ])
  })
  it('leaves an empty goal out', () => {
    const { entries, errors } = validateGoals(draft({ daily: null, weekly: null }))
    expect(entries).toEqual([])
    expect(errors).toEqual({})
  })
  it('words range errors in hours and minutes', () => {
    expect(validateGoals(draft({ daily: 5 })).errors.daily).toBe('Enter between 15 minutes and 24 hours.')
    expect(validateGoals(draft({ weekly: 20000 })).errors.weekly).toBe('Enter between 30 minutes and 168 hours.')
  })
  it('asks for a subject, rejects duplicates and empty durations', () => {
    const { errors } = validateGoals(
      draft({
        subjects: [
          { key: 'a', subject_id: '', minutes: 60 },
          { key: 'b', subject_id: 's1', minutes: 60 },
          { key: 'c', subject_id: 's1', minutes: 60 },
          { key: 'd', subject_id: 's2', minutes: null },
        ],
      }),
    )
    expect(errors['subject-a-subject']).toMatch(/Choose a subject/)
    expect(errors['subject-c-subject']).toMatch(/already has a goal/)
    expect(errors['subject-d']).toMatch(/Enter a weekly goal/)
  })
})
