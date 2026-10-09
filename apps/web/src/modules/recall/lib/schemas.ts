/**
 * What the API sends, checked at the edge with zod. A response that does not match is an error the screen shows as "could
 * not load", never a half-read object deep inside a component. Field names stay snake_case here; `lib/api.ts` is the only
 * place that reads them, and the player works on the camelCase `PlayerCard`.
 */
import { z } from 'zod'

const iso = z.string()
const isoOrNull = iso.nullable()

export const chapterRefSchema = z
  .object({
    id: z.string(),
    key: z.string().nullable(),
    name: z.string().nullable(),
    subject_key: z.string().nullable().optional(),
    subject_name: z.string().nullable().optional(),
  })
  .nullable()

export const sourceSchema = z
  .object({
    origin: z.string().optional(),
    module: z.string().nullable(),
    ref_id: z.string().nullable(),
    locator: z.unknown().optional(),
  })
  .nullable()

/** A card as the review screen needs it: the text, the scheduler's memory and the previews the server would give. */
export const queueCardSchema = z.object({
  id: z.string(),
  rev: z.number(),
  item_id: z.string(),
  item_version_id: z.string(),
  kind: z.string(),
  ordinal: z.number(),
  front_md: z.string(),
  back_md: z.string(),
  state: z.number(),
  badges: z.array(z.string()),
  importance: z.number(),
  chapter: chapterRefSchema,
  previews: z.record(z.string(), z.string()),
  preview_days: z.record(z.string(), z.number()),
  source: sourceSchema,
  stability: z.number().nullable(),
  difficulty: z.number().nullable(),
  due_scheduled_at: isoOrNull,
  postponed_until: isoOrNull,
  due_at: isoOrNull,
  last_review_at: isoOrNull,
  reps: z.number(),
  lapses: z.number(),
  step: z.number().nullable(),
})
export type ApiQueueCard = z.infer<typeof queueCardSchema>

export const settingsSchema = z.object({
  desired_retention: z.number(),
  new_per_day: z.number(),
  reviews_per_day: z.number(),
  learning_steps_min: z.array(z.number()),
  relearning_steps_min: z.array(z.number()),
  max_interval_days: z.number(),
  leech_threshold: z.number(),
  day_start_hour: z.number(),
  tz: z.string(),
  bury_siblings: z.boolean(),
  interleave: z.boolean(),
  catchup_mode: z.string(),
  pause_new_in_catchup: z.boolean(),
  exam_horizon: z.boolean(),
  recall_counts_as_revision: z.boolean(),
  gestures: z.boolean(),
  show_intervals: z.boolean(),
  quick_minutes_per_day: z.number(),
  improve_scheduler_consent: z.boolean(),
  vacation_until: isoOrNull,
  consent_at: isoOrNull,
  scheduler_version: z.string(),
})
export type RecallSettings = z.infer<typeof settingsSchema>

export const queueSchema = z.object({
  source: z.string(),
  server_time: iso,
  cards: z.array(queueCardSchema),
})

export const packSchema = z.object({
  pack_id: z.string(),
  generated_at: iso,
  server_time: iso,
  expires_at: iso,
  settings: settingsSchema,
  weights: z.array(z.number()),
  scheduler_version: z.string(),
  cards: z.array(queueCardSchema),
  counters: z.object({ new_done_today: z.number(), reviews_done_today: z.number(), local_date: z.string() }),
})
export type ApiPack = z.infer<typeof packSchema>

export const forgottenSchema = z.object({
  card_id: z.string(),
  kind: z.string(),
  front_md: z.string(),
  back_md: z.string(),
  subject_key: z.string().nullable(),
  chapter_id: z.string().nullable(),
  importance: z.number(),
  score: z.number(),
  lapses: z.number(),
  agains: z.number(),
  last_again_at: isoOrNull,
})
export type ForgottenCard = z.infer<typeof forgottenSchema>

export const forgottenListSchema = z.object({ items: z.array(forgottenSchema) })

export const todaySchema = z.object({
  server_time: iso,
  local_date: z.string(),
  tz: z.string(),
  mode: z.string(),
  counts: z.object({ new: z.number(), learning: z.number(), due: z.number() }),
  queue_size: z.number(),
  deferred: z.number(),
  days_to_clear: z.number().nullable(),
  est_minutes: z.number(),
  next_due_at: isoOrNull,
  new_available: z.number(),
  limits: z.object({
    new_per_day: z.number(),
    reviews_per_day: z.number(),
    new_done: z.number(),
    reviews_done: z.number(),
  }),
  catchup: z.object({ active: z.boolean(), due: z.number(), oldest_overdue_days: z.number() }),
  vacation_until: isoOrNull,
  streak: z.number(),
  tiles: z.array(
    z.object({ subject_key: z.string().nullable(), total: z.number(), kinds: z.record(z.string(), z.number()) }),
  ),
  forgotten: z.array(forgottenSchema),
  exam: z.unknown().nullable(),
})
export type TodayPlan = z.infer<typeof todaySchema>

/** What a review changes on a card; merged into the local copy by `rev`. */
export const reviewCardSchema = z.object({
  id: z.string(),
  rev: z.number(),
  state: z.number(),
  state_name: z.string(),
  status: z.string(),
  due_at: isoOrNull,
  buried_until: isoOrNull,
  reps: z.number(),
  lapses: z.number(),
  leech: z.boolean(),
  needs_recheck: z.boolean(),
})
export type ReviewCardPatch = z.infer<typeof reviewCardSchema>

/** Every code the server can give one event. All of them are final: the event never needs sending again. */
export const EVENT_STATUSES = [
  'applied',
  'duplicate',
  'applied_to_deleted',
  'stale_content',
  'late_unapplied',
  'invalid',
] as const
export type EventStatus = (typeof EVENT_STATUSES)[number]

export const reviewResultSchema = z.object({
  event_id: z.string(),
  status: z.enum(EVENT_STATUSES),
  reason: z.string(),
  merged: z.boolean(),
  card: reviewCardSchema.nullable(),
})
export type ReviewResult = z.infer<typeof reviewResultSchema>

export const batchResponseSchema = z.object({
  results: z.array(reviewResultSchema),
  cards: z.array(reviewCardSchema),
  server_time: iso,
})

export const undoResponseSchema = z.object({
  undo_id: z.string(),
  voids_id: z.string(),
  card: reviewCardSchema.nullable(),
})

export const sessionSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  source: z.string(),
  status: z.string(),
  started_at: iso,
  ended_at: isoOrNull,
  local_date: z.string(),
  planned_count: z.number(),
  reviewed: z.number(),
})

export const sessionSummarySchema = z.object({
  session_id: z.string(),
  source: z.string(),
  reviewed: z.number(),
  new: z.number(),
  ratings: z.object({ again: z.number(), hard: z.number(), good: z.number(), easy: z.number() }),
  active_seconds: z.number(),
  by_chapter: z.array(z.object({ chapter_id: z.string().nullable(), reviews: z.number(), again: z.number() })),
  streak_after: z.number(),
})
export type SessionSummary = z.infer<typeof sessionSummarySchema>

export const sessionCloseSchema = sessionSchema.extend({ summary: sessionSummarySchema })

export const rebalanceSchema = z.object({}).passthrough()

export const vacationSchema = z.object({ vacation_until: isoOrNull }).passthrough()

export const statsSummarySchema = z.object({
  range: z.string(),
  today: z.string(),
  streak: z.number(),
  longest_streak: z.number(),
  reviews: z.number(),
  new_cards: z.number(),
  minutes: z.number(),
  ratings: z.object({ again: z.number(), hard: z.number(), good: z.number(), easy: z.number() }),
  series: z.array(z.object({ date: z.string(), reviews: z.number(), new: z.number() })),
  true_retention: z.number().nullable(),
})
export type StatsSummary = z.infer<typeof statsSummarySchema>

export const statsRetentionSchema = z.object({
  range: z.string(),
  target: z.number(),
  overall: z.number().nullable(),
  series: z.array(z.object({ date: z.string(), reviews: z.number(), retention: z.number() })),
})
export type StatsRetention = z.infer<typeof statsRetentionSchema>

export const statsForecastSchema = z.object({
  today: z.string(),
  days: z.array(z.object({ date: z.string(), due: z.number() })),
  overdue: z.number(),
})
export type StatsForecast = z.infer<typeof statsForecastSchema>

export const statsChaptersSchema = z.object({
  chapters: z.array(
    z.object({
      chapter: chapterRefSchema,
      cards: z.number(),
      due: z.number(),
      strength: z.number().nullable(),
    }),
  ),
})
export type StatsChapters = z.infer<typeof statsChaptersSchema>

/** A card in the browser and the card screens (W10 builds on it). */
export const cardSchema = z.object({
  id: z.string(),
  rev: z.number(),
  item_id: z.string(),
  item_version_id: z.string(),
  kind: z.string(),
  ordinal: z.number(),
  front_md: z.string(),
  back_md: z.string(),
  fields: z.record(z.string(), z.unknown()),
  state: z.number(),
  state_name: z.string(),
  status: z.string(),
  importance: z.string().or(z.number()),
  chapter: chapterRefSchema,
  subject_key: z.string().nullable(),
  tags: z.array(z.string()),
  reference_keys: z.array(z.string()).optional(),
  deck_ids: z.array(z.string()),
  badges: z.array(z.string()),
  source: sourceSchema,
  due_at: isoOrNull,
  buried_until: isoOrNull,
  reps: z.number(),
  lapses: z.number(),
  created_at: iso,
  updated_at: iso,
})
export type RecallCardRow = z.infer<typeof cardSchema>

export const cardPageSchema = z.object({
  items: z.array(cardSchema),
  next_cursor: z.string().nullable(),
  server_time: iso,
})

/** Her memory of one card, for the card page. */
export const cardMemorySchema = z.object({
  stability: z.number().nullable(),
  difficulty: z.number().nullable(),
  due_scheduled_at: isoOrNull,
  postponed_until: isoOrNull,
  due_at: isoOrNull,
  last_review_at: isoOrNull,
  reps: z.number(),
  lapses: z.number(),
  step: z.number().nullable(),
})
export type CardMemory = z.infer<typeof cardMemorySchema>

export const cardDetailSchema = cardSchema.extend({ memory: cardMemorySchema.optional() })
export type RecallCardDetail = z.infer<typeof cardDetailSchema>

export const createdCardsSchema = z.object({
  item_id: z.string(),
  kind: z.string(),
  existing: z.boolean(),
  cards: z.array(cardDetailSchema),
})

export const deletedCardSchema = z.object({
  deleted: z.boolean(),
  card_id: z.string(),
  undo_token: z.string(),
  undo_seconds: z.number(),
})

export const bulkResultSchema = z.object({ count: z.number() })

export const reviewRowSchema = z.object({
  id: z.string(),
  rating: z.number().nullable(),
  reviewed_at: iso,
  mode: z.string(),
  duration_ms: z.number().nullable(),
  scheduled_days: z.number().nullable(),
  retrievability_before: z.number().nullable(),
})
export type ReviewRow = z.infer<typeof reviewRowSchema>
export const reviewHistorySchema = z.object({ items: z.array(reviewRowSchema) })
