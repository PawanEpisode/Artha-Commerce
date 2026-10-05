/**
 * Activity targets and the confidence gate, mirrored from apps/api/modules/coverage/domain/targets.py.
 * ONE pure module for the screens, the optimistic updates and the tests: both languages are checked against
 * apps/api/modules/coverage/tests/fixtures/rules_cases.json. The server enforces the same rules (409 codes).
 */
import type { ChapterRow, EventType } from './types'

/** A chapter must be at least this covered before confidence can be rated. */
export const CONFIDENCE_MIN_PCT = 50

export type Activity = 'practice' | 'revisions' | 'mocks'
export type LogDecision = 'ok' | 'at_target' | 'not_tracked'

export interface ActivityProgress {
  /** Never above `target`: what the progress card shows as "N of M". */
  done: number
  target: number
  /** The real count. Above `target` only for rows logged before the cap existed. */
  logged: number
  canLog: boolean
}

export const ACTIVITIES: ReadonlyArray<Activity> = ['practice', 'revisions', 'mocks']

export const EVENT_ACTIVITY: Record<EventType, Activity> = {
  practice_done: 'practice',
  revision_done: 'revisions',
  mock_done: 'mocks',
}

export const ACTIVITY_EVENT: Record<Activity, EventType> = {
  practice: 'practice_done',
  revisions: 'revision_done',
  mocks: 'mock_done',
}

/** Plural noun phrases used in hints and toasts ("You have logged all 1 mock tests for this chapter"). */
export const ACTIVITY_NOUN: Record<Activity, string> = {
  practice: 'practice sets',
  revisions: 'revision rounds',
  mocks: 'mock tests',
}

/** A target of 0 means "not tracked". A request past the target is refused whole; legacy counts above it block. */
export function canLog({ count, add = 1, target }: { count: number; add?: number; target: number }): LogDecision {
  if (target <= 0) return 'not_tracked'
  return count + Math.max(add, 1) > target ? 'at_target' : 'ok'
}

export const confidenceAllowed = (coveragePct: number) => coveragePct >= CONFIDENCE_MIN_PCT

export function activityProgress(count: number, target: number): ActivityProgress {
  return {
    done: target > 0 ? Math.min(count, target) : 0,
    target,
    logged: count,
    canLog: canLog({ count, add: 1, target }) === 'ok',
  }
}

/** Per-activity progress of one chapter, clamped, from the facts the API returns (also fine for legacy rows). */
export function chapterActivities(
  chapter: Pick<ChapterRow, 'practice_count' | 'revision_count' | 'mock_count' | 'targets'>,
): Record<Activity, ActivityProgress> {
  return {
    practice: activityProgress(chapter.practice_count, chapter.targets.practice),
    revisions: activityProgress(chapter.revision_count, chapter.targets.revisions),
    mocks: activityProgress(chapter.mock_count, chapter.targets.mocks),
  }
}

/** Why an activity cannot be logged, or null when it can. */
export function logBlockedReason(activity: Activity, progress: ActivityProgress): string | null {
  if (progress.target <= 0) return `${capitalise(ACTIVITY_NOUN[activity])} are not part of your plan.`
  if (!progress.canLog) return `You have logged all ${progress.target} ${ACTIVITY_NOUN[activity]} for this chapter.`
  return null
}

/** Every activity the student tracks is complete: the log form gives way to a done state. */
export function everythingLogged(activities: Record<Activity, ActivityProgress>): boolean {
  const tracked = ACTIVITIES.map((a) => activities[a]).filter((p) => p.target > 0)
  return tracked.length > 0 && tracked.every((p) => !p.canLog)
}

export function confidenceHint(coveragePct: number): string {
  return `Available once this chapter is ${CONFIDENCE_MIN_PCT}% complete. It is at ${coveragePct}% now.`
}

const capitalise = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** "N of M" for a card, clamped, with the real count shown only when it is higher ("2 logged"). */
export function formatProgress(progress: ActivityProgress, unit: string): string {
  const base = `${progress.done} of ${progress.target} ${unit}`
  return progress.logged > progress.target ? `${base} (${progress.logged} logged)` : base
}
