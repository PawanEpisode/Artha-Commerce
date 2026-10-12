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
  needs_recheck: z.boolean().default(false),
  /** `content_changed` (the deck changed the meaning) or `amendment` (a law changed); null when nothing is waiting. */
  recheck_reason: z.string().nullable().default(null),
  /** True for the "Updated" badge: the deck changed this card's meaning. */
  updated: z.boolean().default(false),
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
  /** The exam as an instant (her study day start), so the device applies the same horizon and retention boost. */
  exam_at: isoOrNull.optional(),
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

export const examBlockSchema = z.object({
  exam_date: z.string(),
  days_to_exam: z.number(),
  cram_open: z.boolean(),
  quick: z
    .object({
      candidates: z.number(),
      selected: z.number(),
      cut_off: z.number(),
      per_day: z.number(),
      minutes_per_day: z.number(),
      too_few: z.boolean(),
    })
    .nullable(),
  pacing: z
    .object({
      unseen: z.number(),
      window_days: z.number(),
      new_per_day: z.number(),
      introduced_at_limit: z.number(),
      needed_per_day: z.number(),
      feasible: z.boolean(),
    })
    .nullable(),
})
export type ExamBlock = z.infer<typeof examBlockSchema>

export const quickPlanSchema = z.object({
  exam_date: z.string(),
  days_to_exam: z.number(),
  window_days: z.number(),
  budget_minutes_per_day: z.number(),
  median_seconds: z.number(),
  candidates: z.number(),
  selected: z.number(),
  cut_off: z.number(),
  per_day: z.number(),
  minutes_per_day: z.number(),
  too_few: z.boolean(),
  sample: z.array(queueCardSchema),
})
export type QuickPlan = z.infer<typeof quickPlanSchema>

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
  exam: examBlockSchema.nullable(),
  /** R2-W2: cards waiting for "Still correct", and cards waiting for a chapter of the new syllabus. */
  recheck: z.object({ count: z.number() }).default({ count: 0 }),
  needs_chapter: z.object({ count: z.number() }).default({ count: 0 }),
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
  needs_recheck: z.boolean().default(false),
  /** `content_changed` (the deck changed the meaning) or `amendment` (a law changed); null when nothing is waiting. */
  recheck_reason: z.string().nullable().default(null),
  /** True for the "Updated" badge: the deck changed this card's meaning. */
  updated: z.boolean().default(false),
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
  needs_recheck: z.boolean().default(false),
  /** `content_changed` (the deck changed the meaning) or `amendment` (a law changed); null when nothing is waiting. */
  recheck_reason: z.string().nullable().default(null),
  /** True for the "Updated" badge: the deck changed this card's meaning. */
  updated: z.boolean().default(false),
  source: sourceSchema,
  /** Whether Share may include this card. A selection card is private until she says the words are her own. */
  shareable: z.boolean().default(false),
  /** `required`: the "my own words" statement applies (a card made from a selection, a solution or a mistake). */
  attestation: z
    .object({ required: z.boolean(), attested: z.boolean(), attested_at: isoOrNull })
    .default({ required: false, attested: false, attested_at: null }),
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

/** `POST cards/from-question/`: the created cards plus the id and the 10-second undo token of a new one. */
export const createdQuestionCardSchema = createdCardsSchema.extend({
  card_id: z.string(),
  undo_token: z.string().nullable(),
  undo_seconds: z.number(),
})
export type CreatedQuestionCard = z.infer<typeof createdQuestionCardSchema>

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

// ----------------------------------------------------------------------------------------- platform decks (W11)

export const deckSubscriptionSchema = z
  .object({
    id: z.string(),
    status: z.enum(['active', 'archived']),
    version_no: z.number(),
    /** How many newer versions exist. R1 shows this as a count only (nothing is pulled in until R2). */
    newer_versions: z.number(),
    subscribed_at: iso,
    min_importance: z.string(),
    /** Follow (default) takes updates by itself; pin waits for her to apply them. */
    follow_updates: z.boolean().default(true),
    update_available: z.boolean().default(false),
    pending_changes: z.number().default(0),
    pending_version_no: z.number().nullable().default(null),
    /** The deck was written for the previous syllabus scheme. */
    old_syllabus: z.boolean().default(false),
  })
  .nullable()
export type DeckSubscription = z.infer<typeof deckSubscriptionSchema>

export const deckSchema = z.object({
  id: z.string(),
  slug: z.string(),
  title: z.string(),
  description: z.string(),
  course_id: z.string().nullable(),
  level_id: z.string().nullable(),
  subject_key: z.string().nullable(),
  subject_name: z.string().nullable(),
  chapter_id: z.string().nullable(),
  chapter_name: z.string().nullable(),
  version_no: z.number(),
  item_count: z.number(),
  card_count: z.number(),
  tiers: z.object({ mandatory: z.number(), important: z.number(), bullet: z.number() }).passthrough(),
  published_at: isoOrNull,
  changelog_md: z.string(),
  subscription: deckSubscriptionSchema,
})
export type ApiDeck = z.infer<typeof deckSchema>

export const deckLibrarySchema = z.object({ items: z.array(deckSchema), next_cursor: z.string().nullable() })
export const deckListSchema = z.object({ items: z.array(deckSchema) })

export const deckItemSchema = z.object({
  item_id: z.string(),
  kind: z.string(),
  importance: z.string(),
  position: z.number(),
  preview: z.string(),
  chapter_name: z.string().nullable(),
  /** A law changed and the editors have not checked this card yet. */
  under_review: z.boolean().default(false),
})
export type ApiDeckItem = z.infer<typeof deckItemSchema>

export const deckDetailSchema = z.object({ deck: deckSchema, items: z.array(deckItemSchema) })

export const subscribeResultSchema = z.object({
  created: z.boolean(),
  cards_created: z.number(),
  cards_restored: z.number(),
  deck: deckSchema,
})
export type SubscribeResult = z.infer<typeof subscribeResultSchema>

export const unsubscribeResultSchema = z.object({ deck: deckSchema })
export const reportResultSchema = z.object({ id: z.string(), created: z.boolean() })
export const eraseResultSchema = z.object({ deleted: z.record(z.string(), z.number()) })

// ------------------------------------------------------------------------------- living decks (R2-W2)

export const CHANGE_KINDS = ['added', 'removed', 'typo', 'clarify', 'substantive', 'amendment'] as const
export type ChangeKind = (typeof CHANGE_KINDS)[number]

export const updatePreviewSchema = z.object({
  subscription_id: z.string(),
  update_available: z.boolean(),
  follow_updates: z.boolean(),
  from_version_no: z.number(),
  to_version_no: z.number(),
  versions_skipped: z.number(),
  changelog_md: z.string(),
  /** `{ added, removed, typo, clarify, substantive, amendment, total, recheck }` */
  counts: z.record(z.string(), z.number()),
  /** A few labels per kind (the student's own deck text, shown to her only). */
  items: z.record(z.string(), z.array(z.object({ item_id: z.string(), label: z.string(), importance: z.string() }))),
  more: z.record(z.string(), z.number()).default({}),
  returning_today: z.number(),
})
export type UpdatePreview = z.infer<typeof updatePreviewSchema>

export const syncResultSchema = z.object({
  changed: z.boolean(),
  from_version_no: z.number(),
  to_version_no: z.number(),
  versions_skipped: z.number(),
  added: z.number(),
  removed: z.number(),
  silent: z.number(),
  rechecked: z.number(),
  cards_created: z.number(),
  cards_restored: z.number(),
  cards_archived: z.number(),
  cards_updated: z.number(),
  cards_reset: z.number(),
})
export type SyncResult = z.infer<typeof syncResultSchema>

export const applyUpdateResultSchema = z.object({ result: syncResultSchema, deck: deckSchema })
export const followResultSchema = z.object({ deck: deckSchema })

export const chapterOptionSchema = z.object({ id: z.string(), key: z.string(), name: z.string() }).passthrough()
export const chapterRemapSchema = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      relation: z.string(),
      label: z.string(),
      card_count: z.number(),
      from_chapter: chapterOptionSchema.nullable(),
      candidates: z.array(chapterOptionSchema.nullable()).transform((c) => c.filter((x) => x !== null)),
    }),
  ),
  chapters: z.array(chapterOptionSchema.nullable()).transform((c) => c.filter((x) => x !== null)),
  count: z.number(),
})
export type ChapterRemap = z.infer<typeof chapterRemapSchema>
export type ChapterRemapItem = ChapterRemap['items'][number]
export const chapterChoiceResultSchema = z.object({ id: z.string(), status: z.string(), relation: z.string() })

/** Recall strength of one chapter (FR-F15-65): `cards` is 0 when she has none there. */
export const chapterStrengthSchema = z.object({
  chapter_id: z.string(),
  cards: z.number(),
  due: z.number(),
  strength: z.number().nullable(),
  percent: z.number().nullable(),
})
export type ChapterStrength = z.infer<typeof chapterStrengthSchema>

/** One row of a paste or CSV import, as the server judged it. */
export const importRowSchema = z.object({
  line: z.number(),
  status: z.enum(['ok', 'error', 'created', 'existing']),
  kind: z.string().nullable(),
  front: z.string(),
  back: z.string(),
  issues: z.array(z.object({ field: z.string(), code: z.string(), message: z.string() })),
  card_id: z.string().nullable(),
})
export type ImportRow = z.infer<typeof importRowSchema>

export const importResultSchema = z.object({
  dry_run: z.boolean(),
  total: z.number(),
  valid: z.number(),
  invalid: z.number(),
  created: z.number(),
  existing: z.number(),
  quota: z.object({ room: z.number(), needed: z.number(), fits: z.boolean() }),
  rows: z.array(importRowSchema),
})
export type ImportResult = z.infer<typeof importResultSchema>

// ------------------------------------------------------------------------------- R2-W4: history, attestation, mistakes

export const attestResultSchema = z.object({
  card_id: z.string(),
  changed: z.boolean(),
  required: z.boolean(),
  attested: z.boolean(),
  attested_at: isoOrNull,
  shareable: z.boolean(),
})
export type AttestResult = z.infer<typeof attestResultSchema>

/** One update she received on a deck: the versions, how it came, and counts of what it did. */
export const updateHistorySchema = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      from_version_no: z.number(),
      to_version_no: z.number(),
      versions_skipped: z.number(),
      trigger: z.enum(['auto', 'manual']),
      applied_at: iso,
      /** `{ added, removed, silent, rechecked, cards_created, cards_restored, cards_archived, cards_updated, cards_reset }` */
      counts: z.record(z.string(), z.number()),
      changelog_md: z.string(),
    }),
  ),
})
export type UpdateHistory = z.infer<typeof updateHistorySchema>
export type UpdateHistoryRow = UpdateHistory['items'][number]

export const cardChangesSchema = z.object({
  card_id: z.string(),
  item_id: z.string(),
  platform: z.boolean(),
  waiting: z.number(),
  versions: z.array(
    z.object({
      version_no: z.number(),
      change_kind: z.string(),
      change_note: z.string(),
      at: isoOrNull,
      text: z.string(),
      received: z.boolean(),
      current: z.boolean(),
    }),
  ),
  resets: z.array(z.object({ at: iso, reason: z.string() })),
})
export type CardChanges = z.infer<typeof cardChangesSchema>
export type CardVersionRow = CardChanges['versions'][number]

// ---------------------------------------------------------------------------------------- AI card suggestions (R2-W5)

export const AI_SOURCES = ['notes', 'wrong_answers', 'pasted'] as const
export type AiSource = (typeof AI_SOURCES)[number]

export const aiOverviewSchema = z.object({
  available: z.boolean(),
  consent: z.object({ version: z.string(), given: z.boolean(), given_at: isoOrNull }),
  quota: z.object({
    batches_used: z.number(),
    batches_limit: z.number(),
    suggestions_used: z.number(),
    suggestions_limit: z.number(),
    resets_on: z.string(),
  }),
  sources: z.array(z.string()),
  limits: z.object({
    min_count: z.number(),
    max_count: z.number(),
    default_count: z.number(),
    max_pasted_chars: z.number(),
    min_source_chars: z.number(),
  }),
  waiting_drafts: z.number(),
})
export type AiOverview = z.infer<typeof aiOverviewSchema>

export const aiConsentSchema = z.object({
  version: z.string(),
  title: z.string(),
  points: z.array(z.object({ heading: z.string(), text: z.string() })),
  consented: z.boolean(),
  consented_at: isoOrNull,
  available: z.boolean(),
})
export type AiConsent = z.infer<typeof aiConsentSchema>

export const suggestionSchema = z.object({
  id: z.string(),
  position: z.number(),
  kind: z.string(),
  fields: z.record(z.string(), z.string()),
  front_md: z.string(),
  back_md: z.string(),
  evidence_quote: z.string(),
  evidence_label: z.string(),
  status: z.enum(['draft', 'accepted', 'edited_accepted', 'rejected', 'expired']),
  item_id: z.string().nullable(),
  decided_at: isoOrNull,
})
export type Suggestion = z.infer<typeof suggestionSchema>

export const suggestionBatchSchema = z.object({
  id: z.string(),
  status: z.enum(['queued', 'running', 'ready', 'failed', 'cancelled', 'expired']),
  chapter_id: z.string(),
  sources: z.array(z.string()),
  kinds: z.array(z.string()),
  requested_count: z.number(),
  produced: z.number(),
  dropped: z.number(),
  error_code: z.string().nullable(),
  created_at: z.string(),
  finished_at: isoOrNull,
  expires_at: isoOrNull,
  estimate_seconds: z.number().nullable().optional(),
  reused: z.string().nullable().optional(),
  suggestions: z.array(suggestionSchema),
})
export type SuggestionBatch = z.infer<typeof suggestionBatchSchema>

export const suggestionBatchListSchema = z.object({ results: z.array(suggestionBatchSchema) })

export const acceptSuggestionSchema = createdCardsSchema.extend({ card_id: z.string(), suggestion: suggestionSchema })
export const rejectSuggestionSchema = z.object({ suggestion: suggestionSchema })
export const withdrawConsentSchema = z.object({
  withdrawn: z.boolean(),
  cancelled: z.number(),
  drafts_deleted: z.number(),
})
