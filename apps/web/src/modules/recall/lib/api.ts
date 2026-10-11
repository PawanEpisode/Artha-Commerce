/** Typed calls to `/api/v1/recall/`. Every response goes through its zod schema before the rest of the app sees it. */

import type { z } from 'zod'

import { api } from '~/lib/api'

import { setServerTime } from './clock'
import {
  type ApiPack,
  applyUpdateResultSchema,
  attestResultSchema,
  batchResponseSchema,
  bulkResultSchema,
  cardChangesSchema,
  cardDetailSchema,
  cardPageSchema,
  chapterChoiceResultSchema,
  chapterRemapSchema,
  chapterStrengthSchema,
  createdCardsSchema,
  createdQuestionCardSchema,
  deckDetailSchema,
  deckLibrarySchema,
  deckListSchema,
  deletedCardSchema,
  eraseResultSchema,
  followResultSchema,
  forgottenListSchema,
  importResultSchema,
  packSchema,
  queueSchema,
  quickPlanSchema,
  rebalanceSchema,
  type RecallSettings,
  reportResultSchema,
  reviewHistorySchema,
  sessionCloseSchema,
  sessionSchema,
  settingsSchema,
  statsChaptersSchema,
  statsForecastSchema,
  statsRetentionSchema,
  statsSummarySchema,
  subscribeResultSchema,
  todaySchema,
  undoResponseSchema,
  unsubscribeResultSchema,
  updateHistorySchema,
  updatePreviewSchema,
  vacationSchema,
} from './schemas'

export const QUEUE_SOURCES = ['today', 'chapter', 'deck', 'forgotten', 'catchup', 'quick', 'cram'] as const
export type QueueSource = (typeof QUEUE_SOURCES)[number]
export type ReviewMode = 'normal' | 'catchup' | 'quick_revision' | 'cram' | 'review_ahead'
export type StatsRange = '7d' | '30d' | '90d' | 'all'

const parse = <S extends z.ZodType>(schema: S, data: unknown): z.infer<S> => schema.parse(data)

/** Learns the server's clock from any response that carries `server_time`. */
function learnClock<T extends { server_time?: string }>(data: T): T {
  if (data.server_time) setServerTime(data.server_time)
  return data
}

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ''
}

const jsonBody = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export interface QueueParams {
  chapter_id?: string
  deck_id?: string
  kind?: string
  tier?: string
  limit?: number
  exclude?: string[]
  extra?: number
  tz?: string
}

export const recallApi = {
  today: async (tz?: string) => learnClock(parse(todaySchema, await api<unknown>(`/recall/today/${qs({ tz })}`))),

  queue: async (source: QueueSource, p: QueueParams = {}) =>
    learnClock(
      parse(queueSchema, await api<unknown>(`/recall/queue/${qs({ source, ...p, exclude: p.exclude?.join(',') })}`)),
    ),

  pack: async (limit?: number): Promise<ApiPack> =>
    learnClock(parse(packSchema, await api<unknown>(`/recall/pack/${qs({ limit })}`))),

  settings: async () => parse(settingsSchema, await api<unknown>('/recall/settings/')),

  saveSettings: async (patch: Partial<RecallSettings>) =>
    parse(settingsSchema, await api<unknown>('/recall/settings/', { method: 'PUT', body: JSON.stringify(patch) })),

  setVacation: async (until: string | null) =>
    parse(vacationSchema, await api<unknown>('/recall/vacation/', { method: 'PUT', body: JSON.stringify({ until }) })),

  quickPlan: async (p: { minutes?: number; subject_key?: string; exam_date?: string } = {}) =>
    parse(quickPlanSchema, await api<unknown>(`/recall/quick-revision/plan/${qs(p)}`)),

  forgotten: async (p: { subject_key?: string; limit?: number; window_days?: number } = {}) =>
    parse(forgottenListSchema, await api<unknown>(`/recall/forgotten/${qs(p)}`)).items,

  rebalance: async (days?: number) =>
    parse(rebalanceSchema, await api<unknown>('/recall/catchup/rebalance/', jsonBody(days ? { days } : {}))),

  statsSummary: async (range: StatsRange = '30d') =>
    parse(statsSummarySchema, await api<unknown>(`/recall/stats/summary/${qs({ range })}`)),
  statsRetention: async (range: StatsRange = '30d') =>
    parse(statsRetentionSchema, await api<unknown>(`/recall/stats/retention/${qs({ range })}`)),
  statsForecast: async (days = 30) =>
    parse(statsForecastSchema, await api<unknown>(`/recall/stats/forecast/${qs({ days })}`)),
  /** The recall strength card of a chapter page. 0 cards for a chapter she has none in, never a 404. */
  chapterStrength: async (chapterId: string) =>
    parse(chapterStrengthSchema, await api<unknown>(`/recall/chapters/${chapterId}/strength/`)),

  /**
   * A card from a question she got wrong. The text comes from the question bank on the server (never from here); the same
   * question gives the same card, so a second tap returns it with `existing: true`.
   */
  cardFromQuestion: async (body: {
    question_id: string
    version_id: string
    client_id?: string
    chapter_id?: string
  }) => parse(createdQuestionCardSchema, await api<unknown>('/recall/cards/from-question/', jsonBody(body))),

  /** "These are my own words": makes a selection card shareable, or takes the statement back. Idempotent. */
  attest: async (cardId: string, ownWords: boolean) =>
    parse(attestResultSchema, await api<unknown>(`/recall/cards/${cardId}/attest/`, jsonBody({ own_words: ownWords }))),

  /** The versions of a card's text and the times it came back for a re-check. */
  cardChanges: async (cardId: string) =>
    parse(cardChangesSchema, await api<unknown>(`/recall/cards/${cardId}/changes/`)),

  /** The updates she has received on a deck, newest first. */
  updateHistory: async (subscriptionId: string) =>
    parse(updateHistorySchema, await api<unknown>(`/recall/subscriptions/${subscriptionId}/history/`)).items,

  /** Paste or CSV import. `dry_run` judges every row and writes nothing; `client_id` makes a replay safe. */
  importCards: async (body: ImportBody) =>
    parse(importResultSchema, await api<unknown>('/recall/cards/import/', jsonBody(body))),

  statsChapters: async () => parse(statsChaptersSchema, await api<unknown>('/recall/stats/chapters/')),

  openSession: async (body: {
    client_id: string
    source: string
    spec?: object
    tz?: string
    planned_count?: number
  }) => parse(sessionSchema, await api<unknown>('/recall/sessions/', jsonBody(body))),

  closeSession: async (id: string) =>
    parse(sessionCloseSchema, await api<unknown>(`/recall/sessions/${id}/close/`, jsonBody({}))),

  /** Up to 100 events. Results come back for every event, by `event_id`. */
  submitBatch: async (events: ReviewEventBody[]) =>
    learnClock(parse(batchResponseSchema, await api<unknown>('/recall/reviews/batch/', jsonBody({ events })))),

  undo: async (undoId: string, voidsId: string) =>
    parse(
      undoResponseSchema,
      await api<unknown>('/recall/reviews/undo/', jsonBody({ undo_id: undoId, voids_id: voidsId })),
    ),

  /** Hold a card back from reviews: tomorrow (`bury`) or until the student brings it back (`suspend`). */
  cardAction: async (cardId: string, action: 'bury' | 'suspend') => {
    await api<unknown>(`/recall/cards/${cardId}/${action}/`, jsonBody({}))
  },

  /** Suspend, bring back, bury, reset memory, or confirm a rechecked card. Answers the card. */
  setCardState: async (cardId: string, action: CardStateAction) =>
    parse(cardDetailSchema, await api<unknown>(`/recall/cards/${cardId}/${action}/`, jsonBody({}))),

  card: async (cardId: string) => parse(cardDetailSchema, await api<unknown>(`/recall/cards/${cardId}/`)),

  cardHistory: async (cardId: string) =>
    parse(reviewHistorySchema, await api<unknown>(`/recall/cards/${cardId}/reviews/`)),

  /** `client_id` makes a retry safe: the same id never makes a second card. `force` keeps a duplicate on purpose. */
  createCard: async (body: CreateCardBody) =>
    parse(createdCardsSchema, await api<unknown>('/recall/cards/', jsonBody(body))),

  /** `base_rev` is the revision she started from; a 409 `edit_conflict` carries the server's fields. */
  patchCard: async (cardId: string, body: PatchCardBody) =>
    parse(
      cardDetailSchema,
      await api<unknown>(`/recall/cards/${cardId}/`, { method: 'PATCH', body: JSON.stringify(body) }),
    ),

  deleteCard: async (cardId: string) =>
    parse(deletedCardSchema, await api<unknown>(`/recall/cards/${cardId}/`, { method: 'DELETE' })),

  undoDelete: async (undoToken: string) =>
    parse(cardDetailSchema, await api<unknown>('/recall/cards/undo-delete/', jsonBody({ undo_token: undoToken }))),

  bulkCards: async (ids: string[], action: BulkAction, args: BulkArgs = {}) =>
    parse(bulkResultSchema, await api<unknown>('/recall/cards/bulk/', jsonBody({ ids, action, ...args }))),

  cards: async (p: Record<string, string | number | undefined> = {}) =>
    learnClock(parse(cardPageSchema, await api<unknown>(`/recall/cards/${qs(p)}`))),

  // --- platform decks (W11) ---
  deckLibrary: async (p: DeckLibraryParams = {}) =>
    parse(deckLibrarySchema, await api<unknown>(`/recall/decks/library/${qs({ ...p })}`)),

  myDecks: async () => parse(deckListSchema, await api<unknown>('/recall/decks/subscribed/')).items,

  deck: async (deckId: string) => parse(deckDetailSchema, await api<unknown>(`/recall/decks/${deckId}/`)),

  /** Copies the deck's cards into hers. Safe to repeat: a second tap answers 200 and changes nothing. */
  subscribe: async (deckId: string, body: { min_importance?: Tier } = {}) =>
    parse(subscribeResultSchema, await api<unknown>(`/recall/decks/${deckId}/subscribe/`, jsonBody(body))),

  unsubscribe: async (subscriptionId: string) =>
    parse(
      unsubscribeResultSchema,
      await api<unknown>(`/recall/subscriptions/${subscriptionId}/unsubscribe/`, jsonBody({})),
    ),

  resubscribe: async (subscriptionId: string) =>
    parse(
      subscribeResultSchema,
      await api<unknown>(`/recall/subscriptions/${subscriptionId}/resubscribe/`, jsonBody({})),
    ),

  /** What an update would do (read only), and the apply that does it. Apply is safe to repeat. */
  updatePreview: async (subscriptionId: string) =>
    parse(updatePreviewSchema, await api<unknown>(`/recall/subscriptions/${subscriptionId}/update/`)),

  applyUpdate: async (subscriptionId: string) =>
    parse(
      applyUpdateResultSchema,
      await api<unknown>(`/recall/subscriptions/${subscriptionId}/apply-update/`, jsonBody({})),
    ),

  setFollow: async (subscriptionId: string, follow: boolean) =>
    parse(
      followResultSchema,
      await api<unknown>(`/recall/subscriptions/${subscriptionId}/`, {
        method: 'PATCH',
        body: JSON.stringify({ follow_updates: follow }),
      }),
    ),

  chapterRemaps: async () => parse(chapterRemapSchema, await api<unknown>('/recall/chapter-remaps/')),

  chooseChapter: async (remapId: string, chapterId: string) =>
    parse(
      chapterChoiceResultSchema,
      await api<unknown>(`/recall/chapter-remaps/${remapId}/choose/`, jsonBody({ chapter_id: chapterId })),
    ),

  reportItem: async (itemId: string, body: { reason: ReportReason; note?: string }) =>
    parse(reportResultSchema, await api<unknown>(`/recall/items/${itemId}/report/`, jsonBody(body))),

  // --- her data (W11): open even when the feature is switched off ---
  exportJson: async () => api<unknown>('/recall/export/'),

  erase: async (confirm: string) =>
    parse(eraseResultSchema, await api<unknown>('/recall/erase/', jsonBody({ confirm }))),
}

export type Tier = 'bullet' | 'important' | 'mandatory'
export type ReportReason = 'wrong' | 'outdated' | 'copyright' | 'other'
export interface DeckLibraryParams {
  tier?: Tier
  subject_key?: string
  chapter_id?: string
  cursor?: string
  limit?: number
}

export type CardStateAction = 'suspend' | 'unsuspend' | 'bury' | 'reset' | 'recheck-ok'
export type BulkAction = 'move_chapter' | 'set_importance' | 'add_tag' | 'suspend' | 'delete' | 'add_to_deck'
export interface BulkArgs {
  chapter_id?: string | null
  importance?: 'bullet' | 'important' | 'mandatory'
  tag?: string
  deck_id?: string
}

export interface ImportBody {
  client_id: string
  dry_run: boolean
  text: string
  chapter_id?: string | null
  importance?: 'bullet' | 'important' | 'mandatory'
}

export interface CreateCardBody {
  client_id: string
  kind: string
  fields: Record<string, string>
  chapter_id?: string | null
  topic_id?: string | null
  importance?: 'bullet' | 'important' | 'mandatory'
  tags?: string[]
  deck_ids?: string[]
  force?: boolean
}

export interface PatchCardBody {
  base_rev: number
  fields?: Record<string, string>
  importance?: 'bullet' | 'important' | 'mandatory'
  tags?: string[]
  chapter_id?: string | null
  topic_id?: string | null
}

/** One review as sent to the server. No card text ever travels back: only ids, the rating and the timing. */
export interface ReviewEventBody {
  id: string
  card_id: string
  rating: 1 | 2 | 3 | 4
  reviewed_at: string
  duration_ms: number | null
  session_id: string | null
  mode: ReviewMode
  item_version_id: string | null
  device_id: string | null
  tz_offset_min: number
}
