/**
 * Product events for the recall screens (PRD F-15 10.1). Every property goes through an allow-list per event and must be a
 * boolean, a number or a short token made of lower-case letters, digits, `_` and `-`. A card's text, a note or a name
 * cannot get through: a free string fails the token test and the property is dropped.
 */
import { track } from '~/modules/observability'

const ALLOWED = {
  recall_session_started: ['source', 'mode', 'planned', 'offline', 'first'],
  recall_card_viewed: ['first', 'kind', 'state'],
  recall_review_undone: ['within_seconds'],
  recall_catchup_started: ['due_total', 'overdue_days_max', 'queue_size'],
  recall_catchup_cleared: ['days_taken'],
  recall_rebalance_used: ['moved', 'days'],
  recall_leech_shown: ['lapses'],
  recall_leech_action: ['lapses', 'action'],
  recall_sync_completed: ['events', 'merged', 'dropped_deleted', 'dropped_stale', 'duration_ms'],
  recall_settings_changed: ['changed_keys', 'retention'],
  recall_pack_downloaded: ['cards', 'bytes_bucket'],
} as const satisfies Record<string, readonly string[]>

export type RecallEvent = keyof typeof ALLOWED

const TOKEN = /^[a-z0-9_-]{1,32}$/

export const allowedProperties = (event: RecallEvent): readonly string[] => ALLOWED[event]

/** Keeps only the allowed, safe-looking properties of an event. Exported for the allow-list test. */
export function cleanProperties(
  event: RecallEvent,
  props: Record<string, unknown>,
): Record<string, boolean | number | string> {
  const out: Record<string, boolean | number | string> = {}
  const allowed: readonly string[] = ALLOWED[event]
  for (const [key, value] of Object.entries(props)) {
    if (!allowed.includes(key)) continue
    if (typeof value === 'boolean') out[key] = value
    else if (typeof value === 'number' && Number.isFinite(value)) out[key] = value
    else if (typeof value === 'string' && TOKEN.test(value)) out[key] = value
  }
  return out
}

export function trackRecall(event: RecallEvent, props: Record<string, unknown> = {}) {
  track(event, cleanProperties(event, props))
}
