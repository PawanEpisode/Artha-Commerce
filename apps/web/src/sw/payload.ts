import { DEFAULT_DEEP_LINK, safeDeepLink } from './deeplink'

/**
 * Push payload version 1 (PRD 9.4). The worker must show a notification for every push (browsers require it), so
 * parsing never throws and always returns something showable: a message it did not understand becomes a plain
 * "you have an update" notification that opens the app.
 */
export const PAYLOAD_VERSION = 1
export const FALLBACK_TITLE = 'ArthaCommerce'
export const FALLBACK_BODY = 'You have a new update.'
export const FALLBACK_TAG = 'artha-update'

const MAX_TITLE = 120
const MAX_BODY = 300
const MAX_ACTIONS = 2
const TAG_PATTERN = /^[\w:.-]{1,80}$/
const ID_PATTERN = /^[\w-]{1,64}$/

export interface PushAction {
  id: string
  title: string
}

export interface NotificationContent {
  title: string
  body: string
  /** Same tag, same alert: a second push for the same moment replaces the first. */
  tag: string
  /** Allow-listed relative path. */
  url: string
  /** Notification id, when the payload had a usable one. */
  id: string | null
  category: string | null
  actions: PushAction[]
}

export type ParseFailure = 'empty' | 'invalid_json' | 'not_object' | 'unsupported_version' | 'invalid_fields'

export type ParseResult =
  | { recognised: true; content: NotificationContent }
  | { recognised: false; reason: ParseFailure; content: NotificationContent }

export const fallbackContent = (): NotificationContent => ({
  title: FALLBACK_TITLE,
  body: FALLBACK_BODY,
  tag: FALLBACK_TAG,
  url: DEFAULT_DEEP_LINK,
  id: null,
  category: null,
  actions: [],
})

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const text = (value: unknown, max: number): string => (typeof value === 'string' ? value.trim().slice(0, max) : '')

function parseActions(value: unknown): PushAction[] {
  if (!Array.isArray(value)) return []
  const actions: PushAction[] = []
  for (const item of value) {
    if (!isRecord(item)) continue
    const id = text(item.id, 32)
    const title = text(item.title, 40)
    if (id && title) actions.push({ id, title })
    if (actions.length === MAX_ACTIONS) break
  }
  return actions
}

/** Turns the raw push body (JSON text, or null for an empty push) into what to show. Pure and total. */
export function parsePushPayload(raw: string | null | undefined): ParseResult {
  const failed = (reason: ParseFailure): ParseResult => ({ recognised: false, reason, content: fallbackContent() })
  if (raw === null || raw === undefined || raw.trim() === '') return failed('empty')

  let data: unknown
  try {
    data = JSON.parse(raw)
  } catch {
    return failed('invalid_json')
  }
  if (!isRecord(data)) return failed('not_object')
  // A version this worker does not know may mean different fields. Show the generic message, never guess.
  if (data.v !== PAYLOAD_VERSION) return failed('unsupported_version')

  const title = text(data.title, MAX_TITLE)
  if (!title) return failed('invalid_fields')

  const id = typeof data.id === 'string' && ID_PATTERN.test(data.id) ? data.id : null
  const tag = typeof data.tag === 'string' && TAG_PATTERN.test(data.tag) ? data.tag : FALLBACK_TAG
  const category = typeof data.category === 'string' && ID_PATTERN.test(data.category) ? data.category : null

  return {
    recognised: true,
    content: {
      title,
      body: text(data.body, MAX_BODY),
      tag,
      url: safeDeepLink(data.url),
      id,
      category,
      actions: parseActions(data.actions),
    },
  }
}
