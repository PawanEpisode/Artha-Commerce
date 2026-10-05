import { formatDuration } from '@artha/design-system'

import { GOAL_DAILY_MAX, GOAL_DAILY_MIN, GOAL_WEEKLY_MAX, GOAL_WEEKLY_MIN } from './limits'
import type { GoalEntry } from './types'

export interface SubjectGoalDraft {
  /** Stable React key; the row's position changes when another row is removed. */
  key: string
  subject_id: string
  minutes: number | null
}

export interface GoalsDraft {
  /** Whole minutes; null leaves the goal out (and removes it on save). */
  daily: number | null
  weekly: number | null
  subjects: SubjectGoalDraft[]
}

export type GoalErrors = Record<string, string>

const range = (min: number, max: number) =>
  `Enter between ${formatDuration(min, 'long')} and ${formatDuration(max, 'long')}.`

/** Entries to send plus per-field messages. Empty goals are left out; the server removes goals that are not sent. */
export function validateGoals(draft: GoalsDraft): { entries: GoalEntry[]; errors: GoalErrors } {
  const errors: GoalErrors = {}
  const entries: GoalEntry[] = []
  const check = (
    key: string,
    minutes: number | null,
    period: 'daily' | 'weekly',
    min: number,
    max: number,
    subject_id: string | null,
  ) => {
    if (minutes === null) return false
    if (minutes < min || minutes > max) errors[key] = range(min, max)
    else entries.push({ period, subject_id, target_minutes: minutes })
    return true
  }
  check('daily', draft.daily, 'daily', GOAL_DAILY_MIN, GOAL_DAILY_MAX, null)
  check('weekly', draft.weekly, 'weekly', GOAL_WEEKLY_MIN, GOAL_WEEKLY_MAX, null)
  const seen = new Set<string>()
  for (const row of draft.subjects) {
    const key = `subject-${row.key}`
    if (!row.subject_id) {
      if (row.minutes !== null) errors[`${key}-subject`] = 'Choose a subject for this goal.'
      continue
    }
    if (seen.has(row.subject_id)) {
      errors[`${key}-subject`] = 'This subject already has a goal. Remove one of them.'
      continue
    }
    seen.add(row.subject_id)
    if (row.minutes === null) errors[key] = 'Enter a weekly goal for this subject, or remove the row.'
    else check(key, row.minutes, 'weekly', GOAL_WEEKLY_MIN, GOAL_WEEKLY_MAX, row.subject_id)
  }
  return { entries, errors }
}
