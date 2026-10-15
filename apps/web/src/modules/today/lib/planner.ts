import type {
  Health,
  Milestone,
  MilestoneKind,
  NextAttemptOption,
  OptionName,
  ReplanEvent,
  ReplanOption,
  ReplanTrigger,
  StudyPlan,
} from './planner-types'
import { formatDay, formatMinutes } from './time'

export type Tone = 'good' | 'warn' | 'bad' | 'quiet'

export interface HealthView {
  label: string
  tone: Tone
  headline: string
}

/** What the health card says (PRD 7.x). The numbers are the plan's, so the sentence never disagrees with the bar. */
export function healthView(plan: Pick<StudyPlan, 'health' | 'shortfall_minutes' | 'remaining_minutes'>): HealthView {
  switch (plan.health) {
    case 'on_track':
      return { label: 'On track', tone: 'good', headline: 'Your reading fits the time you have left.' }
    case 'slightly_behind':
      return {
        label: 'Slightly behind',
        tone: 'warn',
        headline: `You are about ${formatMinutes(plan.shortfall_minutes)} short of finishing the reading in time.`,
      }
    case 'at_risk':
      return {
        label: 'At risk',
        tone: 'bad',
        headline: `You are about ${formatMinutes(plan.shortfall_minutes)} short of finishing the reading in time.`,
      }
    default:
      return { label: 'No plan to check', tone: 'quiet', headline: 'There is nothing left to plan before your exam.' }
  }
}

/** How full the reading window is: remaining work against what fits, 0 to 100 (more than the window holds shows as full). */
export function capacityPercent(plan: Pick<StudyPlan, 'capacity_minutes' | 'remaining_minutes'>): number {
  if (plan.remaining_minutes <= 0) return 0
  if (plan.capacity_minutes <= 0) return 100
  return Math.min(100, Math.round((100 * plan.remaining_minutes) / plan.capacity_minutes))
}

export function milestoneTitle(m: Pick<Milestone, 'kind' | 'subject_name' | 'subject_key'>): string {
  const paper = m.subject_name || m.subject_key
  const titles: Record<MilestoneKind, string> = {
    finish_reading: `Finish reading ${paper}`,
    first_revision: `First revision of ${paper}`,
    mock: `Mock test: ${paper}`,
    exam_week: 'Exam week: no new reading',
  }
  return titles[m.kind]
}

/** "Moved 6 days later", "Moved 1 day earlier", or null when it has not moved. */
export function movedNote(m: Pick<Milestone, 'moved_days'>): string | null {
  if (m.moved_days === 0) return null
  const n = Math.abs(m.moved_days)
  return `Moved ${n} ${n === 1 ? 'day' : 'days'} ${m.moved_days > 0 ? 'later' : 'earlier'}`
}

/** The note beside an open milestone: overdue, at risk, or null. */
export function statusNote(m: Pick<Milestone, 'status' | 'overdue_days'>): string | null {
  if (m.status === 'done') return 'Done'
  if (m.status === 'dropped') return 'No longer in your course'
  if (m.overdue_days > 0) return `Overdue by ${m.overdue_days} ${m.overdue_days === 1 ? 'day' : 'days'}`
  if (m.status === 'at_risk') return 'At risk'
  return null
}

export interface MilestoneGroups {
  open: Milestone[]
  finished: Milestone[]
}

/** Open milestones by date (the server's order breaks ties), then the ones already done or dropped. */
export function groupMilestones(list: readonly Milestone[]): MilestoneGroups {
  const open: Milestone[] = []
  const finished: Milestone[] = []
  for (const m of list) (m.status === 'done' || m.status === 'dropped' ? finished : open).push(m)
  open.sort((a, b) => a.target_date.localeCompare(b.target_date))
  return { open, finished }
}

export interface OptionView {
  name: OptionName
  title: string
  detail: string
  feasible: boolean
  confirm: string
}

const nextAttemptDetail = (o: NextAttemptOption): string =>
  o.exam_date === null
    ? 'There is no later attempt in your course yet.'
    : o.feasible
      ? `Move your exam to ${formatDay(o.exam_date)}. Your reading would then fit.`
      : `Move your exam to ${formatDay(o.exam_date)}. You would still be about ${formatMinutes(o.shortfall_minutes ?? 0)} short.`

/** One card per option: what choosing it does, in numbers, and the words for the confirm button. */
export function optionView(option: ReplanOption): OptionView {
  switch (option.option) {
    case 'more_time':
      return {
        name: 'more_time',
        title: 'Study a little more each day',
        detail: option.feasible
          ? `Go to ${formatMinutes(option.daily_minutes)} a day (${formatMinutes(option.extra_minutes)} more). Your reading would fit.`
          : `You would need ${formatMinutes(option.daily_minutes)} a day, which is more than a day can hold.`,
        feasible: option.feasible,
        confirm: 'Use more time',
      }
    case 'skim_low_weight':
      return {
        name: 'skim_low_weight',
        title: 'Skim the low-weight chapters',
        detail: option.feasible
          ? `Skim ${option.chapter_count} ${option.chapter_count === 1 ? 'chapter' : 'chapters'} that carry the fewest marks per minute and save ${formatMinutes(option.saved_minutes)}.`
          : `Skimming everything would save ${formatMinutes(option.saved_minutes)}, which is still not enough.`,
        feasible: option.feasible,
        confirm: 'Skim those chapters',
      }
    case 'next_attempt':
      return {
        name: 'next_attempt',
        title: 'Sit the next attempt',
        detail: nextAttemptDetail(option),
        feasible: option.feasible,
        confirm: 'Move my exam',
      }
  }
}

const TRIGGER_WORDS: Record<ReplanTrigger, string> = {
  missed_days: 'after missed days',
  weekly: 'in the weekly check',
  manual: 'when you asked',
  exam_date: 'after your exam date changed',
  scheme_switch: 'after your syllabus changed',
}

export const triggerWords = (trigger: ReplanTrigger) => TRIGGER_WORDS[trigger]

/** "Your plan was re-planned when you asked: 3 dates moved." One line for the note under the health card. */
export function replanSummary(event: Pick<ReplanEvent, 'trigger' | 'moved_count' | 'health_after'>): string {
  const when = `Your plan was re-planned ${triggerWords(event.trigger)}`
  if (event.moved_count === 0) return `${when}. Nothing needed to move.`
  return `${when}: ${event.moved_count} ${event.moved_count === 1 ? 'date' : 'dates'} moved.`
}

const HEALTH_RANK: Record<Health, number> = { unknown: 0, on_track: 1, slightly_behind: 2, at_risk: 3 }

/** True when the plan got worse between two checks (the card then asks for a look, not just a note). */
export const gotWorse = (before: Health, after: Health) => HEALTH_RANK[after] > HEALTH_RANK[before]

/** "Next automatic check: Mon 19 Oct", or null when there is none before the exam. */
export const nextReplanText = (plan: Pick<StudyPlan, 'next_replan_on'>): string | null =>
  plan.next_replan_on ? `Next automatic check: ${formatDay(plan.next_replan_on)}` : null
