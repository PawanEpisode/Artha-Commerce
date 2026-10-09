/** Builders shared by the recall tests. Not exported from the module. */
import { DEFAULT_WEIGHTS } from './fsrs6'
import type { ApiPack, ApiQueueCard, RecallSettings } from './schemas'

export const SETTINGS: RecallSettings = {
  desired_retention: 0.9,
  new_per_day: 100,
  reviews_per_day: 200,
  learning_steps_min: [1, 10],
  relearning_steps_min: [10],
  max_interval_days: 365,
  leech_threshold: 8,
  day_start_hour: 4,
  tz: 'Asia/Kolkata',
  bury_siblings: true,
  interleave: true,
  catchup_mode: 'auto',
  pause_new_in_catchup: true,
  exam_horizon: true,
  recall_counts_as_revision: true,
  gestures: true,
  show_intervals: true,
  quick_minutes_per_day: 30,
  improve_scheduler_consent: false,
  vacation_until: null,
  consent_at: null,
  scheduler_version: 'fsrs-6.0',
}

export function apiCard(i: number, over: Partial<ApiQueueCard> = {}): ApiQueueCard {
  const id = `00000000-0000-4000-8000-${String(i).padStart(12, '0')}`
  return {
    id,
    rev: 1,
    item_id: `10000000-0000-4000-8000-${String(i).padStart(12, '0')}`,
    item_version_id: `20000000-0000-4000-8000-${String(i).padStart(12, '0')}`,
    kind: 'definition',
    ordinal: 0,
    front_md: `Question ${i}`,
    back_md: `Answer ${i}`,
    state: 0,
    badges: [],
    importance: i % 3,
    chapter: { id: 'c1', key: 'ch-1', name: 'Chapter one', subject_key: i % 2 === 0 ? 'law' : 'audit' },
    previews: {},
    preview_days: {},
    source: null,
    stability: null,
    difficulty: null,
    due_scheduled_at: null,
    postponed_until: null,
    due_at: null,
    last_review_at: null,
    reps: 0,
    lapses: 0,
    step: null,
    ...over,
  }
}

export function apiPack(cards: ApiQueueCard[], over: Partial<ApiPack> = {}): ApiPack {
  return {
    pack_id: 'pack-1',
    generated_at: '2026-10-09T06:00:00Z',
    server_time: '2026-10-09T06:00:00Z',
    expires_at: '2026-10-09T12:00:00Z',
    settings: SETTINGS,
    weights: [...DEFAULT_WEIGHTS],
    scheduler_version: 'fsrs-6.0',
    cards,
    counters: { new_done_today: 0, reviews_done_today: 0, local_date: '2026-10-09' },
    ...over,
  }
}

/** A small seeded random generator so a failing run can be repeated. */
export function rng(seed: number): () => number {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

import type { TodayPlan } from './schemas'

export function todayPlan(over: Partial<TodayPlan> = {}): TodayPlan {
  return {
    server_time: '2026-10-09T08:00:00Z',
    local_date: '2026-10-09',
    tz: 'Asia/Kolkata',
    mode: 'normal',
    counts: { new: 5, learning: 2, due: 13 },
    queue_size: 20,
    deferred: 0,
    days_to_clear: 1,
    est_minutes: 12,
    next_due_at: '2026-10-09T10:00:00Z',
    new_available: 30,
    limits: { new_per_day: 10, reviews_per_day: 100, new_done: 0, reviews_done: 0 },
    catchup: { active: false, due: 0, oldest_overdue_days: 0 },
    vacation_until: null,
    streak: 4,
    tiles: [{ subject_key: 'law', total: 12, kinds: { definition: 12 } }],
    forgotten: [],
    exam: null,
    ...over,
  }
}
