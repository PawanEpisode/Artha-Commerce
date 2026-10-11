/** The sentences of the exam screens. Pure, so the wording and the plurals can be tested. */

import { plural } from './format'
import type { ExamBlock, QuickPlan } from './schemas'

type Pacing = NonNullable<ExamBlock['pacing']>

/** "36 days to your exam", "Tomorrow", "Your exam is today": the count is whole days, rounded down. */
export function countdown(days: number, cramOpen: boolean): string {
  if (cramOpen) return 'Your exam is within a day'
  const d = Math.max(Math.floor(days), 0)
  if (d === 0) return 'Your exam is today'
  if (d === 1) return 'Your exam is tomorrow'
  return `${d} days to your exam`
}

/** What the pacing assistant says. It never blames: it states the arithmetic and one way out. */
export function pacingMessage(p: Pacing): string {
  if (p.unseen === 0) return 'Every card in your syllabus has been seen at least once.'
  if (p.window_days === 0) return `${plural(p.unseen, 'card')} are still new. The introduction window has closed.`
  if (p.feasible) {
    return `${plural(p.unseen, 'card')} are still new. At ${p.new_per_day} new a day you will have seen them all about two weeks before the exam.`
  }
  return `${plural(p.unseen, 'card')} are still new. At ${p.new_per_day} new a day you will have seen ${p.introduced_at_limit} of them by two weeks before the exam. Raise new cards to ${p.needed_per_day} a day to see them all.`
}

/** The quick revision summary line under the plan heading. */
export function quickSummary(
  plan: Pick<QuickPlan, 'selected' | 'window_days' | 'per_day' | 'minutes_per_day'>,
): string {
  if (plan.selected === 0) return 'Nothing needs quick revision.'
  return `${plural(plan.selected, 'card')} over ${plural(plan.window_days, 'day')}: about ${plan.per_day} a day, ${plan.minutes_per_day} min.`
}

/** What was left out, said kindly. */
export function cutOffSentence(cutOff: number): string | null {
  return cutOff > 0
    ? `${plural(cutOff, 'card')} did not fit your daily time. They stay in your normal reviews. Add minutes to bring them in.`
    : null
}
